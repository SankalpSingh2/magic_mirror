import open3d as o3d
import argparse
import os


def load_off(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"OFF file not found: {path}")
    mesh = o3d.io.read_triangle_mesh(path)
    if not mesh.has_triangles():
        raise ValueError("Loaded mesh has no triangles.")
    print(f"Loaded mesh: {path} | Vertices: {len(mesh.vertices)}, Triangles: {len(mesh.triangles)}")
    return mesh


def smooth_mesh(mesh, iterations=10, lambda_val=0.5):
    return mesh.filter_smooth_laplacian(number_of_iterations=iterations, lambda_lambda=lambda_val)


def convert_off_to_stl(input_off, output_stl, smooth=False, iterations=10):
    mesh = load_off(input_off)

    # Compute normals if they don't exist
    if not mesh.has_vertex_normals():
        print("Computing vertex normals...")
        mesh.compute_vertex_normals()

    if not mesh.has_triangle_normals():
        print("Computing triangle normals...")
        mesh.compute_triangle_normals()

    if smooth:
        print("Smoothing mesh...")
        mesh = smooth_mesh(mesh, iterations)
        # Recompute normals after smoothing
        mesh.compute_vertex_normals()
        mesh.compute_triangle_normals()

    print(f"Writing STL to: {output_stl}")
    o3d.io.write_triangle_mesh(output_stl, mesh)
    print("Conversion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert OFF to STL using Open3D.")
    parser.add_argument("input_off", help="Path to the input .off file")
    parser.add_argument("output_stl", help="Path to the output .stl file")
    parser.add_argument("--smooth", action="store_true", help="Apply Laplacian smoothing")
    parser.add_argument("--iterations", type=int, default=10, help="Smoothing iterations (default: 10)")

    args = parser.parse_args()
    convert_off_to_stl(args.input_off, args.output_stl, smooth=args.smooth, iterations=args.iterations)
