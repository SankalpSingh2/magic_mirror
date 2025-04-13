import genesis as gs
import numpy as np
import trimesh
import os


def extract_accurate_heightmap(stl_path, grid_size=100):
    """Generate a more accurate heightmap from an STL file"""
    # Load the mesh with trimesh
    mesh = trimesh.load_mesh(stl_path)

    # Make sure mesh is centered in XY
    mesh.vertices -= mesh.centroid
    mesh.vertices[:, 2] -= np.min(mesh.vertices[:, 2])  # Set minimum height to zero

    # Get bounds
    min_bound = mesh.bounds[0]
    max_bound = mesh.bounds[1]

    # Create grid for heightmap
    x_range = np.linspace(min_bound[0], max_bound[0], grid_size)
    y_range = np.linspace(min_bound[1], max_bound[1], grid_size)

    # Initialize heightmap - start with lowest possible height
    heightmap = np.zeros((grid_size, grid_size))

    # For performance, we'll use trimesh's built-in ray intersection
    # Create a grid of ray origins and directions
    origins = np.zeros((grid_size, grid_size, 3))
    for i, x in enumerate(x_range):
        for j, y in enumerate(y_range):
            origins[i, j] = [x, y, max_bound[2] + 1.0]

    # Reshape for vectorized operation
    origins_flat = origins.reshape(-1, 3)
    directions_flat = np.tile([0, 0, -1], (origins_flat.shape[0], 1))

    # Perform ray intersections
    locations, index_ray, index_tri = mesh.ray.intersects_location(
        origins_flat, directions_flat)

    # Convert intersection locations back to heights
    if len(locations) > 0:
        # Map ray indices back to grid positions
        for loc, ray_idx in zip(locations, index_ray):
            i = ray_idx // grid_size
            j = ray_idx % grid_size
            # Since rays could hit multiple faces, take the highest point
            heightmap[i, j] = max(heightmap[i, j], loc[2])

    # Fill in any missed points using nearest neighbor interpolation
    valid_points = heightmap > 0
    if not np.all(valid_points):
        # Create coordinate grids
        x_grid, y_grid = np.meshgrid(range(grid_size), range(grid_size))
        valid_coords = np.column_stack((x_grid[valid_points], y_grid[valid_points]))
        valid_heights = heightmap[valid_points]

        # Get coordinates of invalid points
        invalid_coords = np.column_stack((x_grid[~valid_points], y_grid[~valid_points]))

        # For each invalid point, find nearest valid point
        for i, (x, y) in enumerate(invalid_coords):
            # Calculate distances to all valid points
            distances = np.sqrt(np.sum((valid_coords - np.array([x, y])) ** 2, axis=1))
            # Get index of minimum distance
            nearest_idx = np.argmin(distances)
            # Set height to that of nearest valid point
            heightmap[x, y] = valid_heights[nearest_idx]

    return heightmap, (min_bound, max_bound)


def main():
    # Initialize Genesis
    gs.init(backend=gs.gpu)

    # Create a scene with customized simulation options
    scene = gs.Scene(
        sim_options=gs.options.SimOptions(
            dt=0.005,  # Smaller timestep for more accurate simulation
            substeps=2,  # More substeps for better stability
            gravity=(0.0, 0.0, -15.0),  # Stronger gravity (-15 instead of -9.81)
            floor_height=-100000,  # Floor below the terrain to avoid interference
        ),
        show_viewer=True,
        viewer_options=gs.options.ViewerOptions(
            camera_pos=(3.5, 0.0, 2.5),
            camera_lookat=(0.0, 0.0, 0.5),
            camera_fov=40,
        ),
    )

    # Parameters
    stl_path = "/home/pchitiveli/catapult/Genesis/output_stl1.stl"  # Your STL file path
    grid_size = 200  # Higher resolution for better accuracy

    # Generate heightmap
    print("Generating accurate heightmap from STL...")
    heightmap, (min_bound, max_bound) = extract_accurate_heightmap(stl_path, grid_size)

    # Calculate dimensions
    x_size = max_bound[0] - min_bound[0]
    y_size = max_bound[1] - min_bound[1]
    max_height = np.max(heightmap)

    print(f"Terrain dimensions: x_size={x_size}, y_size={y_size}, max_height={max_height}")

    # Create the terrain entity
    terrain = scene.add_entity(
        gs.morphs.Terrain(
            pos=(0, 0, 0),
            visualization=True,
            collision=True,
            n_subterrains=(1, 1),
            subterrain_size=(x_size, y_size),
            horizontal_scale=x_size / grid_size,
            vertical_scale=1.0,  # We've already scaled the heightmap correctly
            height_field=heightmap
        ),
        surface=gs.surfaces.Default(color=(0.7, 0.7, 0.7, 1.0)),
        material=gs.materials.Rigid(friction=0.8)  # Added friction for better interaction
    )

    # Add the ground plane
    scene.add_entity(
        gs.morphs.Plane(
            pos=(0, 0, -0.5),  # Place it at or below floor_height
        ),
        material=gs.materials.Rigid(friction=0.9),
        surface=gs.surfaces.Default(color=(0.5, 0.5, 0.5, 1.0))
    )

    # Add spheres directly at their initial positions
    spheres = []

    # First add the initial 5 active spheres
    for i in range(5):
        x_pos = np.random.uniform(-x_size / 4, x_size / 4)
        y_pos = np.random.uniform(-y_size / 4, y_size / 4)
        z_pos = max_height + 1.5 + i * 0.5

        print(f"Adding initial sphere {i} at position ({x_pos}, {y_pos}, {z_pos})")

        sphere = scene.add_entity(
            gs.morphs.Sphere(
                pos=(x_pos, y_pos, z_pos),
                radius=0.1 + i * 0.02,  # Smaller increments for better visibility
                collision=True
            ),
            surface=gs.surfaces.Default(
                color=(np.random.uniform(0.2, 0.8),
                       np.random.uniform(0.2, 0.8),
                       np.random.uniform(0.2, 0.8), 1.0)
            ),
            material=gs.materials.Rigid()  # Added some bounciness
        )
        spheres.append(sphere)

    # Then add the remaining 5 spheres in hidden positions
    for i in range(5, 10):
        sphere = scene.add_entity(
            gs.morphs.Sphere(
                pos=(0, 0, -100),  # Initial hidden position
                radius=0.1 + i * 0.02,  # Smaller increments
                collision=True
            ),
            surface=gs.surfaces.Default(
                color=(np.random.uniform(0.2, 0.8),
                       np.random.uniform(0.2, 0.8),
                       np.random.uniform(0.2, 0.8), 1.0)
            ),
            material=gs.materials.Rigid()  # Added some bounciness
        )
        spheres.append(sphere)

    # Build the scene once after all entities are added
    print("Building scene...")
    scene.build()

    # Track how many spheres have been activated
    activated_spheres = 5  # First 5 are already active

    # Run simulation
    print("Running simulation...")
    for step in range(1000):
        if step > 0 and step % 100 == 0 and activated_spheres < 10:
            # Activate a new sphere
            x_pos = np.random.uniform(-x_size / 4, x_size / 4)
            y_pos = np.random.uniform(-y_size / 4, y_size / 4)
            z_pos = max_height + 3.0

            print(f"Activating sphere {activated_spheres} at position ({x_pos}, {y_pos}, {z_pos})")

            # Use the Genesis API to set the position
            spheres[activated_spheres].pos = (x_pos, y_pos, z_pos)
            activated_spheres += 1

        scene.step()


if __name__ == "__main__":
    main()