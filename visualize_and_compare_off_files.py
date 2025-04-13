import open3d as o3d
import numpy as np
import argparse
import os
import sys


def visualize_off_file(file_path, window_name=None):
    """
    Visualize an OFF file using Open3D.

    Args:
        file_path (str): Path to the OFF file
        window_name (str, optional): Custom window name for visualization
    """
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return False

    # Check file extension
    if not file_path.lower().endswith('.off'):
        print(f"Warning: File {file_path} does not have an .off extension.")

    # Load the mesh
    try:
        mesh = o3d.io.read_triangle_mesh(file_path)
    except Exception as e:
        print(f"Error loading mesh: {e}")
        return False

    # Basic mesh info
    print(f"Mesh loaded: {file_path}")
    print(f"Vertices: {len(mesh.vertices)}")
    print(f"Triangles: {len(mesh.triangles)}")
    print(f"Has vertex colors: {mesh.has_vertex_colors()}")

    # If no vertex normals, compute them for better visualization
    if not mesh.has_vertex_normals():
        mesh.compute_vertex_normals()
        print("Computed vertex normals for visualization.")

    # Create a coordinate frame for reference
    coordinate_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
        size=0.5, origin=[0, 0, 0])

    # Set window name if provided
    if window_name:
        window_title = window_name
    else:
        window_title = f"Open3D - {os.path.basename(file_path)}"

    # Visualize the mesh
    o3d.visualization.draw_geometries(
        [mesh, coordinate_frame],
        window_name=window_title,
        width=1024,
        height=768,
        point_show_normal=False,
        mesh_show_back_face=True
    )

    return True


def compare_off_files(file1, file2):
    """
    Visualize two OFF files side by side for comparison.

    Args:
        file1 (str): Path to the first OFF file
        file2 (str): Path to the second OFF file
    """
    # Load the meshes
    try:
        mesh1 = o3d.io.read_triangle_mesh(file1)
        mesh2 = o3d.io.read_triangle_mesh(file2)
    except Exception as e:
        print(f"Error loading meshes: {e}")
        return False

    # Compute normals if needed
    if not mesh1.has_vertex_normals():
        mesh1.compute_vertex_normals()
    if not mesh2.has_vertex_normals():
        mesh2.compute_vertex_normals()

    # Create visualization windows
    vis1 = o3d.visualization.Visualizer()
    vis1.create_window(window_name=f"Original: {os.path.basename(file1)}", width=800, height=600, left=0, top=0)
    vis1.add_geometry(mesh1)
    vis1.add_geometry(o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.5, origin=[0, 0, 0]))

    vis2 = o3d.visualization.Visualizer()
    vis2.create_window(window_name=f"Modified: {os.path.basename(file2)}", width=800, height=600, left=800, top=0)
    vis2.add_geometry(mesh2)
    vis2.add_geometry(o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.5, origin=[0, 0, 0]))

    # Run visualizations
    while True:
        if not vis1.poll_events() or not vis2.poll_events():
            break
        vis1.update_renderer()
        vis2.update_renderer()

    vis1.destroy_window()
    vis2.destroy_window()

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize OFF files using Open3D")
    parser.add_argument("files", nargs='+', help="Path to OFF file(s) to visualize")
    parser.add_argument("--compare", action="store_true", help="Compare two OFF files side by side")
    parser.add_argument("--window-name", help="Custom window name for visualization")

    args = parser.parse_args()

    if args.compare and len(args.files) == 2:
        compare_off_files(args.files[0], args.files[1])
    elif len(args.files) == 1:
        visualize_off_file(args.files[0], args.window_name)
    else:
        # Visualize files one after another
        for file in args.files:
            visualize_off_file(file)