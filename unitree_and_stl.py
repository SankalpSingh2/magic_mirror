import os
import pickle
import numpy as np
import trimesh
import torch
from importlib import metadata
import genesis as gs
import tkinter as tk
from tkinter import filedialog, ttk
from threading import Thread

# ---------------------------------------------------------------------
# Ensure correct RSL-RL library is installed
# ---------------------------------------------------------------------
try:
    try:
        if metadata.version("rsl-rl"):
            raise ImportError
    except metadata.PackageNotFoundError:
        if metadata.version("rsl-rl-lib") != "2.2.4":
            raise ImportError
except (metadata.PackageNotFoundError, ImportError) as e:
    raise ImportError("Please uninstall 'rsl_rl' and install 'rsl-rl-lib==2.2.4'.") from e

from rsl_rl.runners import OnPolicyRunner
from custom_go2_env import CustomGo2Env

# ---------------------------------------------------------------------
# STL to heightmap extraction
# ---------------------------------------------------------------------
def extract_accurate_heightmap(stl_path, grid_size=100):
    mesh = trimesh.load_mesh(stl_path)
    mesh.vertices -= mesh.centroid
    mesh.vertices[:, 2] -= np.min(mesh.vertices[:, 2])
    
    min_bound = mesh.bounds[0]
    max_bound = mesh.bounds[1]
    
    x_range = np.linspace(min_bound[0], max_bound[0], grid_size)
    y_range = np.linspace(min_bound[1], max_bound[1], grid_size)
    heightmap = np.zeros((grid_size, grid_size))
    
    origins = np.zeros((grid_size, grid_size, 3))
    for i, x in enumerate(x_range):
        for j, y in enumerate(y_range):
            origins[i, j] = [x, y, max_bound[2] + 1.0]
    
    origins_flat = origins.reshape(-1, 3)
    directions_flat = np.tile([0, 0, -1], (origins_flat.shape[0], 1))
    
    locations, index_ray, _ = mesh.ray.intersects_location(origins_flat, directions_flat)
    
    if len(locations) > 0:
        for loc, ray_idx in zip(locations, index_ray):
            i = ray_idx // grid_size
            j = ray_idx % grid_size
            heightmap[i, j] = max(heightmap[i, j], loc[2])
    
    valid_points = heightmap > 0
    if not np.all(valid_points):
        x_grid, y_grid = np.meshgrid(range(grid_size), range(grid_size))
        valid_coords = np.column_stack((x_grid[valid_points], y_grid[valid_points]))
        valid_heights = heightmap[valid_points]
        invalid_coords = np.column_stack((x_grid[~valid_points], y_grid[~valid_points]))
        
        for i, (x, y) in enumerate(invalid_coords):
            distances = np.sqrt(np.sum((valid_coords - np.array([x, y]))**2, axis=1))
            nearest_idx = np.argmin(distances)
            heightmap[x, y] = valid_heights[nearest_idx]
    
    return heightmap, (min_bound, max_bound)

# ---------------------------------------------------------------------
# Simulation function (to be called from GUI)
# ---------------------------------------------------------------------
def run_simulation(stl_path, exp_name, ckpt, grid_size, robot_pos_x, robot_pos_y, height_offset, yaw_angle, fix_orientation, status_callback=None):
    if status_callback:
        status_callback("Initializing Genesis...")
    
    gs.init(backend=gs.gpu)

    # Load environment configs
    log_dir = f"{os.path.expanduser('~')}/catapult/logs/{exp_name}"
    cfg_path = f"{log_dir}/cfgs.pkl"
    if os.path.exists(cfg_path):
        if status_callback:
            status_callback(f"Loading configs from {cfg_path}")
        env_cfg, obs_cfg, reward_cfg, command_cfg, train_cfg = pickle.load(open(cfg_path, "rb"))
        reward_cfg["reward_scales"] = {}
    else:
        error_msg = f"Missing cfgs.pkl at {cfg_path}"
        if status_callback:
            status_callback(f"ERROR: {error_msg}")
        raise FileNotFoundError(error_msg)

    # Load STL + extract heightmap
    if status_callback:
        status_callback(f"Generating heightmap from STL: {os.path.basename(stl_path)}")
    heightmap, (min_bound, max_bound) = extract_accurate_heightmap(stl_path, grid_size)
    x_size = max_bound[0] - min_bound[0]
    y_size = max_bound[1] - min_bound[1]
    max_height = np.max(heightmap)
    if status_callback:
        status_callback(f"Terrain: x={x_size:.2f}, y={y_size:.2f}, max_h={max_height:.2f}")
    
    # Modify robot spawn height based on terrain and user inputs
    env_cfg["base_init_pos"] = [robot_pos_x, robot_pos_y, max_height + height_offset]
    
    # Fix robot orientation if requested
    if fix_orientation:
        # Set the robot's initial orientation to be upright
        # Convert yaw angle from degrees to radians
        yaw_rad = np.radians(yaw_angle)
        
        # Create quaternion for the yaw rotation (rotation around Z axis)
        # Order: w, x, y, z (real part first)
        quat = [np.cos(yaw_rad/2), 0, 0, np.sin(yaw_rad/2)]
        
        # Update the init orientation in the environment config
        env_cfg["base_init_quat"] = quat
        
        if status_callback:
            status_callback(f"Robot placement: x={robot_pos_x}, y={robot_pos_y}, z={max_height + height_offset}, yaw={yaw_angle}°")
            status_callback(f"Robot orientation fixed with quaternion: {quat}")
    else:
        if status_callback:
            status_callback(f"Robot placement: x={robot_pos_x}, y={robot_pos_y}, z={max_height + height_offset}")
            status_callback("Using default robot orientation")
    
    # Create a custom scene with terrain first
    if status_callback:
        status_callback("Creating scene with terrain...")
    scene = gs.Scene(
        sim_options=gs.options.SimOptions(
            dt=0.02,  # To match the dt in Go2Env
            substeps=2,
            gravity=(0.0, 0.0, -15.0),
            floor_height=-100000,
        ),
        show_viewer=True,
        viewer_options=gs.options.ViewerOptions(
            camera_pos=(3.5, 0.0, 2.5),
            camera_lookat=(0.0, 0.0, 0.5),
            camera_fov=40,
            max_FPS=int(0.5 / 0.02),  # Match FPS setting with dt
        ),
        rigid_options=gs.options.RigidOptions(
            dt=0.02,
            constraint_solver=gs.constraint_solver.Newton,
            enable_collision=True,
            enable_joint_limit=True,
        ),
        vis_options=gs.options.VisOptions(rendered_envs_idx=list(range(1))),
    )
    
    scene.add_entity(
        gs.morphs.Terrain(
            pos=(0, 0, 0),
            visualization=True,
            collision=True,
            n_subterrains=(1, 1),
            subterrain_size=(x_size, y_size),
            horizontal_scale=x_size / grid_size,
            vertical_scale=1.0,
            height_field=heightmap,
        ),
        surface=gs.surfaces.Default(color=(0.7, 0.7, 0.7, 0.01)),
        material=gs.materials.Rigid(friction=0.8),
    )

    # Add the STL mesh for visualization
    scene.add_entity(     
        gs.morphs.Mesh(
            file=stl_path,
            pos=(0, 0, 0),
            scale=1.0,
            visualization=True,
            collision=False,
            fixed=True
        ),
        surface=gs.surfaces.Default(color=(0.7, 0.7, 0.7, 1.0)),
    )
    
    # Create environment with our custom scene
    if status_callback:
        status_callback("Loading CustomGo2Env with terrain...")
    env = CustomGo2Env(
        num_envs=1,
        env_cfg=env_cfg,
        obs_cfg=obs_cfg,
        reward_cfg=reward_cfg,
        command_cfg=command_cfg,
        show_viewer=False,  # We've already set up the viewer in our scene
        custom_scene=scene,
    )
    
    # Load policy
    if status_callback:
        status_callback("Loading policy...")
    runner = OnPolicyRunner(env, train_cfg, log_dir, device=gs.device)
    resume_path = os.path.join(log_dir, f"model_{ckpt}.pt")
    runner.load(resume_path)
    policy = runner.get_inference_policy(device=gs.device)

    # Reset environment to place robot
    obs, _ = env.get_observations()

    if status_callback:
        status_callback("Simulation running with learned policy!")
    
    for _ in range(1000):
        with torch.no_grad():
            actions = policy(obs)
            obs, _, terminated, info = env.step(actions)
            
        # If terminated, reset the environment
        if terminated.any():
            if status_callback:
                status_callback("Robot terminated. Resetting...")
            # obs, _ = env.reset()

# ---------------------------------------------------------------------
# GUI Application
# ---------------------------------------------------------------------
class TerrainSimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Go2 Terrain Simulator")
        self.geometry("600x700")
        
        # Default values
        self.stl_path = tk.StringVar()
        self.exp_name = tk.StringVar(value="go2-walking")
        self.ckpt = tk.IntVar(value=100)
        self.grid_size = tk.IntVar(value=200)
        
        # Robot positioning values
        self.robot_pos_x = tk.DoubleVar(value=4.0)
        self.robot_pos_y = tk.DoubleVar(value=4.0)
        self.height_offset = tk.DoubleVar(value=0.5)
        
        # Robot orientation values
        self.fix_orientation = tk.BooleanVar(value=True)
        self.yaw_angle = tk.DoubleVar(value=0.0)
        
        self.create_widgets()
    
    def create_widgets(self):
        # Create frames for organization
        file_frame = ttk.LabelFrame(self, text="STL File Selection")
        file_frame.pack(fill="x", padx=10, pady=10)
        
        params_frame = ttk.LabelFrame(self, text="Simulation Parameters")
        params_frame.pack(fill="x", padx=10, pady=10)
        
        robot_frame = ttk.LabelFrame(self, text="Robot Placement")
        robot_frame.pack(fill="x", padx=10, pady=10)
        
        orientation_frame = ttk.LabelFrame(self, text="Robot Orientation")
        orientation_frame.pack(fill="x", padx=10, pady=10)
        
        status_frame = ttk.LabelFrame(self, text="Status")
        status_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # STL File selection
        ttk.Label(file_frame, text="STL File:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(file_frame, textvariable=self.stl_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(file_frame, text="Browse...", command=self.browse_stl).grid(row=0, column=2, padx=5, pady=5)
        
        # Parameters
        ttk.Label(params_frame, text="Experiment Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(params_frame, textvariable=self.exp_name).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(params_frame, text="Checkpoint:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(params_frame, textvariable=self.ckpt).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(params_frame, text="Grid Size:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(params_frame, textvariable=self.grid_size).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        params_frame.columnconfigure(1, weight=1)
        
        # Robot positioning
        ttk.Label(robot_frame, text="Robot X Position:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(robot_frame, textvariable=self.robot_pos_x, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(robot_frame, text="Robot Y Position:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(robot_frame, textvariable=self.robot_pos_y, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(robot_frame, text="Height Offset:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(robot_frame, textvariable=self.height_offset, width=10).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(robot_frame, text="(Z will be terrain height + offset)").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        
        robot_frame.columnconfigure(1, weight=1)
        
        # Robot orientation
        ttk.Checkbutton(
            orientation_frame, 
            text="Fix Robot Orientation (prevent upside-down spawning)", 
            variable=self.fix_orientation
        ).grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        
        ttk.Label(orientation_frame, text="Yaw Angle (degrees):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(orientation_frame, textvariable=self.yaw_angle, width=10).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(orientation_frame, text="(0-360, rotation around Z axis)").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        
        orientation_frame.columnconfigure(1, weight=1)
        
        # Status text and run button
        self.status_text = tk.Text(status_frame, height=10, wrap=tk.WORD)
        self.status_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create a scrollbar
        scrollbar = ttk.Scrollbar(self.status_text, command=self.status_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.status_text.config(yscrollcommand=scrollbar.set)
        
        # Add some initial status text
        self.status_text.insert(tk.END, "Ready. Select an STL file and configure parameters to start.\n")
        self.status_text.insert(tk.END, "NOTE: 'Fix Robot Orientation' option is enabled by default to prevent upside-down spawning.\n")
        self.status_text.config(state=tk.DISABLED)  # Make it read-only
        
        # Run button
        run_button = ttk.Button(self, text="Run Simulation", command=self.run_simulation_thread)
        run_button.pack(pady=10)
    
    def browse_stl(self):
        filetypes = [("STL Files", "*.stl"), ("All Files", "*.*")]
        filename = filedialog.askopenfilename(title="Select STL File", filetypes=filetypes)
        if filename:
            self.stl_path.set(filename)
            self.update_status(f"Selected STL file: {os.path.basename(filename)}")
    
    def update_status(self, message):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.update_idletasks()
    
    def run_simulation_thread(self):
        # Validate inputs
        if not self.stl_path.get():
            self.update_status("ERROR: Please select an STL file first")
            return
        
        try:
            ckpt = self.ckpt.get()
            grid_size = self.grid_size.get()
            robot_pos_x = self.robot_pos_x.get()
            robot_pos_y = self.robot_pos_y.get()
            height_offset = self.height_offset.get()
            fix_orientation = self.fix_orientation.get()
            yaw_angle = self.yaw_angle.get()
            
            if grid_size <= 0:
                raise ValueError("Grid size must be positive")
            
            # Normalize yaw angle to 0-360 range
            yaw_angle = yaw_angle % 360
            
        except Exception as e:
            self.update_status(f"ERROR: Invalid parameters - {str(e)}")
            return
        
        # Clear status and update
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.update_status("Starting simulation...")
        
        # Run in a separate thread to keep GUI responsive
        simulation_thread = Thread(
            target=run_simulation,
            args=(
                self.stl_path.get(),
                self.exp_name.get(),
                ckpt,
                grid_size,
                robot_pos_x,
                robot_pos_y,
                height_offset,
                yaw_angle,
                fix_orientation,
                self.update_status
            )
        )
        simulation_thread.daemon = True
        simulation_thread.start()

# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app = TerrainSimulatorApp()
    app.mainloop()