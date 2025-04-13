import numpy as np
import open3d as o3d
import trimesh
import os
import argparse
from scipy.spatial import KDTree
from tqdm import tqdm


def process_point_cloud(input_pcd_path=None, voxel_size=0.01,
                        outlier_nb_neighbors=20, outlier_std_ratio=2.0,
                        normal_radius=0.1, normal_max_nn=50):
    """
    Process a point cloud from file or dataset to prepare for meshing.
    Returns the processed point cloud.
    """
    # Load point cloud
    if input_pcd_path:
        print(f"Loading point cloud from {input_pcd_path}")
        pcd = o3d.io.read_point_cloud(input_pcd_path)
    else:
        print("No point cloud specified, loading from sample dataset")
        dataset = o3d.data.OfficePointClouds()
        pcds = []
        for pcd_path in dataset.paths:
            pcds.append(o3d.io.read_point_cloud(pcd_path))
        pcd = pcds[13]  # Default to the 13th sample

    print(f"Point cloud has {len(pcd.points)} points")

    # Downsample if needed
    if voxel_size > 0:
        print(f"Downsampling with voxel size {voxel_size}")
        pcd = pcd.voxel_down_sample(voxel_size=voxel_size)
        print(f"After downsampling: {len(pcd.points)} points")

    # Remove outliers
    print(f"Removing statistical outliers (neighbors={outlier_nb_neighbors}, std ratio={outlier_std_ratio})")
    pcd, _ = pcd.remove_statistical_outlier(
        nb_neighbors=outlier_nb_neighbors,
        std_ratio=outlier_std_ratio
    )
    print(f"After outlier removal: {len(pcd.points)} points")

    # Estimate normals
    print("Estimating normals")
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=normal_radius, max_nn=normal_max_nn
        )
    )

    # Orient normals
    print("Orienting normals")
    pcd.orient_normals_consistent_tangent_plane(100)

    return pcd


def create_mesh_from_point_cloud(pcd, method="ball_pivoting",
                                 poisson_depth=9, poisson_width=0,
                                 ball_pivoting_radius_multipliers=[0.5, 1.0, 2.0]):
    """
    Create a mesh from a point cloud using the specified method.
    Returns the created mesh.
    """
    print(f"Creating mesh using {method} method")

    if method == "ball_pivoting":
        # Calculate average distance between points
        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = sum(distances) / len(distances)
        radii = [avg_dist * x for x in ball_pivoting_radius_multipliers]

        print(f"Ball pivoting with radii: {radii}")
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, o3d.utility.DoubleVector(radii)
        )
    elif method == "poisson":
        print(f"Poisson reconstruction with depth={poisson_depth}, width={poisson_width}")
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=poisson_depth, width=poisson_width, scale=1.1, linear_fit=False
        )
    else:
        raise ValueError(f"Unknown meshing method: {method}")

    # Clean up the mesh
    print("Cleaning mesh")
    mesh.remove_duplicated_vertices()
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()
    mesh.remove_non_manifold_edges()

    print(f"Created mesh with {len(mesh.vertices)} vertices and {len(mesh.triangles)} triangles")
    return mesh


def load_off_file(file_path):
    """Load an OFF file using trimesh and convert to Open3D point cloud."""
    mesh = trimesh.load_mesh(file_path)
    points = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)

    # Extract colors/textures if available
    vertex_colors = None
    if hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
        vertex_colors = mesh.visual.vertex_colors
    elif hasattr(mesh.visual, 'face_colors') and mesh.visual.face_colors is not None:
        # Convert face colors to vertex colors if needed
        face_colors = mesh.visual.face_colors
        vertex_colors = np.zeros((len(points), 4), dtype=np.uint8)
        for i, face in enumerate(faces):
            for vertex_idx in face:
                vertex_colors[vertex_idx] = face_colors[i]

    # Convert to Open3D objects
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    # Add colors to point cloud if available
    if vertex_colors is not None:
        pcd.colors = o3d.utility.Vector3dVector(vertex_colors[:, :3].astype(float) / 255.0)

    # Estimate normals (helpful for RANSAC)
    pcd.estimate_normals()

    return pcd, mesh, points, faces, vertex_colors


def compute_feature_importance(pcd, points):
    """Compute importance weights for each point based on geometric features."""
    print("Computing feature importance weights")
    # Compute curvature estimate for each point
    normals = np.asarray(pcd.normals)
    kdtree = o3d.geometry.KDTreeFlann(pcd)

    curvatures = np.zeros(len(points))
    importance = np.ones(len(points))

    # For each point, estimate curvature based on normal variation in neighborhood
    k = 30  # Number of neighbors to consider
    for i, point in tqdm(enumerate(points), total=len(points), desc="Analyzing curvature"):
        # Find k nearest neighbors
        _, idx, _ = kdtree.search_knn_vector_3d(point, k)
        if len(idx) < 2:
            continue

        # Get normals of neighbors
        neighbor_normals = normals[idx]

        # Compute variance of normals as a curvature estimate
        mean_normal = np.mean(neighbor_normals, axis=0)
        mean_normal = mean_normal / np.linalg.norm(mean_normal)

        # Calculate the dot product between each normal and the mean normal
        alignments = np.abs(np.sum(neighbor_normals * mean_normal, axis=1))
        curvature = 1.0 - np.mean(alignments)  # Higher value means higher curvature

        curvatures[i] = curvature

    # Normalize curvatures to [0, 1] range
    if np.max(curvatures) > np.min(curvatures):
        curvatures = (curvatures - np.min(curvatures)) / (np.max(curvatures) - np.min(curvatures))

    # Higher curvature means higher importance (less smoothing)
    importance = 1.0 + 9.0 * curvatures  # Scale to [1, 10]

    return importance


def adaptive_ransac_plane_segmentation(pcd, points, importance_weights,
                                       min_distance=0.005, max_distance=0.02,
                                       ransac_n=3, num_iterations=2000,
                                       min_plane_size=100):
    """Use RANSAC to segment planes in the point cloud with adaptive thresholds based on importance."""
    print("Starting adaptive RANSAC plane segmentation")
    planes = []
    plane_points = []
    plane_indices = []

    # Create a copy of the point cloud
    remaining_pcd = o3d.geometry.PointCloud()
    remaining_pcd.points = o3d.utility.Vector3dVector(np.asarray(pcd.points))
    if hasattr(pcd, 'colors') and pcd.colors:
        remaining_pcd.colors = o3d.utility.Vector3dVector(np.asarray(pcd.colors))
    if hasattr(pcd, 'normals') and pcd.normals:
        remaining_pcd.normals = o3d.utility.Vector3dVector(np.asarray(pcd.normals))

    remaining_points = np.asarray(pcd.points)
    remaining_indices = np.arange(len(points))

    # Continue until we can't extract more significant planes
    min_points = max(min_plane_size, len(remaining_points) * 0.01)  # At least 1% of points or min_plane_size

    while len(remaining_points) > min_points:
        # Apply RANSAC
        plane_model, inliers = remaining_pcd.segment_plane(
            distance_threshold=max_distance,  # Start with max threshold
            ransac_n=ransac_n,
            num_iterations=num_iterations
        )

        if len(inliers) < min_points:
            break  # Stop if the plane is too small

        # Get original point indices
        original_indices = remaining_indices[inliers]

        # Refine inliers based on importance weights
        refined_inliers = []
        for i, idx in enumerate(inliers):
            orig_idx = remaining_indices[idx]
            weight = importance_weights[orig_idx]

            # Calculate adjusted threshold based on importance
            # High importance = smaller threshold (preserve detail)
            # Low importance = larger threshold (more smoothing)
            adjusted_threshold = max_distance - (weight - 1) / 9.0 * (max_distance - min_distance)

            # Check if point is still an inlier with adjusted threshold
            a, b, c, d = plane_model
            point = remaining_points[idx]
            dist = abs(a * point[0] + b * point[1] + c * point[2] + d) / np.sqrt(a * a + b * b + c * c)

            if dist <= adjusted_threshold:
                refined_inliers.append(idx)

        # Skip this plane if too few refined inliers
        if len(refined_inliers) < min_points:
            # Remove just the first 20% of inliers and continue
            remove_count = max(int(len(inliers) * 0.2), 1)
            outlier_indices = list(range(len(remaining_indices)))
            for i in sorted(inliers[:remove_count], reverse=True):
                outlier_indices.remove(i)

            outlier_pcd = remaining_pcd.select_by_index(inliers[:remove_count], invert=True)
            remaining_pcd = outlier_pcd
            remaining_points = np.asarray(remaining_pcd.points)
            remaining_indices = remaining_indices[outlier_indices]
            continue

        # Store the plane and its points
        planes.append(plane_model)
        points_in_plane = remaining_points[refined_inliers]
        original_indices_in_plane = remaining_indices[refined_inliers]
        plane_points.append(points_in_plane)
        plane_indices.append(original_indices_in_plane)

        # Remove these points and continue
        outlier_pcd = remaining_pcd.select_by_index(refined_inliers, invert=True)
        remaining_pcd = outlier_pcd
        remaining_points = np.asarray(remaining_pcd.points)

        # Update remaining_indices by removing refined_inliers
        mask = np.ones(len(remaining_indices), dtype=bool)
        mask[refined_inliers] = False
        remaining_indices = remaining_indices[mask]

        print(f"Plane {len(planes)} extracted with {len(refined_inliers)} points")

    # Add remaining points as small regions (no smoothing)
    if len(remaining_points) > 0:
        print(f"Adding {len(remaining_points)} non-planar points")
        plane_points.append(remaining_points)
        plane_indices.append(remaining_indices)

    return planes, plane_points, plane_indices, remaining_indices


def adaptive_project_points_to_planes(points, planes, plane_indices, importance_weights):
    """Project points to their assigned plane with adaptive smoothing based on importance."""
    print("Projecting points to planes with adaptive smoothing")
    projected_points = np.zeros_like(points)
    plane_assignments = np.full(len(points), -1, dtype=int)

    # First assign points that were used to define planes
    for i, indices in enumerate(plane_indices):
        if i < len(planes):  # We have a plane model
            plane = planes[i]
            for idx in indices:
                plane_assignments[idx] = i

                # Get original point
                point = points[idx]

                # Get importance weight (higher = less smoothing)
                weight = importance_weights[idx]
                smoothing_factor = 1.0 - (weight - 1.0) / 9.0  # Convert [1,10] to [1,0]

                # Project point to plane with adaptive smoothing
                if i < len(planes):  # It's a proper plane, not just remaining points
                    a, b, c, d = plane
                    normal = np.array([a, b, c])
                    normal = normal / np.linalg.norm(normal)

                    # Formula for projection of point onto plane
                    distance_to_plane = a * point[0] + b * point[1] + c * point[2] + d
                    pure_projection = point - distance_to_plane * normal

                    # Apply weighted smoothing
                    projected_points[idx] = point * (1 - smoothing_factor) + pure_projection * smoothing_factor
                else:
                    # For non-plane regions, keep original points
                    projected_points[idx] = point
        else:
            # These are remaining points without a plane
            for idx in indices:
                plane_assignments[idx] = -1
                projected_points[idx] = points[idx]  # Keep original

    # For any unassigned points, find nearest plane or keep original
    if -1 in plane_assignments:
        # Create KD trees for each plane's points
        plane_kdtrees = []
        for i, plane_pts in enumerate(plane_indices):
            if len(plane_pts) > 0:
                tree = KDTree(points[plane_pts])
                plane_kdtrees.append((i, tree))

        unassigned_points = np.where(plane_assignments == -1)[0]
        for i in tqdm(unassigned_points, desc="Processing unassigned points"):
            point = points[i]
            # Find nearest plane
            min_dist = float('inf')
            best_plane_idx = -1

            for plane_idx, tree in plane_kdtrees:
                dist, _ = tree.query(point, k=1)
                if dist < min_dist:
                    min_dist = dist
                    best_plane_idx = plane_idx

            # If we found a close plane, use it
            if best_plane_idx != -1 and best_plane_idx < len(planes):
                plane = planes[best_plane_idx]
                plane_assignments[i] = best_plane_idx

                # Apply adaptive smoothing based on importance
                weight = importance_weights[i]
                smoothing_factor = 1.0 - (weight - 1.0) / 9.0

                # Project to plane
                a, b, c, d = plane
                normal = np.array([a, b, c])
                normal = normal / np.linalg.norm(normal)

                distance_to_plane = a * point[0] + b * point[1] + c * point[2] + d
                pure_projection = point - distance_to_plane * normal

                # Apply weighted smoothing
                projected_points[i] = point * (1 - smoothing_factor) + pure_projection * smoothing_factor
            else:
                # Keep original point
                projected_points[i] = point

    return projected_points, plane_assignments


def transfer_colors(original_mesh, original_vertex_colors, smoothed_vertices):
    """Transfer colors from original mesh to smoothed mesh."""
    if original_vertex_colors is None:
        return trimesh.Trimesh(vertices=smoothed_vertices, faces=original_mesh.faces)

    # Create smoothed mesh with same colors
    smoothed_mesh = trimesh.Trimesh(
        vertices=smoothed_vertices,
        faces=original_mesh.faces,
        vertex_colors=original_vertex_colors
    )

    return smoothed_mesh


def smooth_mesh_ransac(mesh_file, output_file, min_distance=0.005, max_distance=0.02,
                       feature_sensitivity=1.0, visualize=True):
    """Smooth a mesh file using adaptive RANSAC plane fitting."""
    # Load the mesh file
    pcd, original_mesh, points, faces, vertex_colors = load_off_file(mesh_file)
    print(f"Loaded mesh with {len(points)} vertices and {len(faces)} faces")

    # Compute feature importance for adaptive smoothing
    importance_weights = compute_feature_importance(pcd, points)
    importance_weights = 1.0 + feature_sensitivity * (importance_weights - 1.0)  # Adjust sensitivity

    # Segment the point cloud into planes using adaptive RANSAC
    planes, plane_points, plane_indices, remaining_indices = adaptive_ransac_plane_segmentation(
        pcd,
        points,
        importance_weights,
        min_distance=min_distance,
        max_distance=max_distance,
        min_plane_size=max(50, len(points) // 200)  # Adjust based on mesh size
    )
    print(f"Found {len(planes)} planes")

    # Visualize the segmentation if requested
    if visualize:
        remaining_points = points[remaining_indices] if len(remaining_indices) > 0 else np.array([])
        visualize_segmentation(points, plane_points, remaining_points)

    # Project points onto nearest planes with adaptive smoothing
    projected_points, plane_assignments = adaptive_project_points_to_planes(
        points, planes, plane_indices, importance_weights
    )

    # Create smoothed mesh with color transfer
    smoothed_mesh = transfer_colors(original_mesh, vertex_colors, projected_points)

    # Save the result
    print(f"Saving to {output_file}...")
    smoothed_mesh.export(output_file)

    return smoothed_mesh


def convert_to_stl(input_file, output_file, smooth=False, iterations=10, lambda_val=0.5):
    """Convert a mesh file to STL format with optional smoothing."""
    print(f"Converting {input_file} to STL format")

    # Load the mesh
    mesh = o3d.io.read_triangle_mesh(input_file)

    # Compute normals if they don't exist
    if not mesh.has_vertex_normals():
        print("Computing vertex normals...")
        mesh.compute_vertex_normals()

    if not mesh.has_triangle_normals():
        print("Computing triangle normals...")
        mesh.compute_triangle_normals()

    # Apply Laplacian smoothing if requested
    if smooth:
        print(f"Applying Laplacian smoothing (iterations={iterations}, lambda={lambda_val})")
        mesh = mesh.filter_smooth_laplacian(number_of_iterations=iterations, lambda_lambda=lambda_val)
        # Recompute normals after smoothing
        mesh.compute_vertex_normals()
        mesh.compute_triangle_normals()

    # Save as STL
    print(f"Writing to {output_file}")
    o3d.io.write_triangle_mesh(output_file, mesh)
    print("Conversion complete")

    return mesh


def visualize_segmentation(original_points, plane_points, remaining_points=None):
    """Visualize the original points and segmented planes."""
    print("Visualizing segmentation")
    # Create Open3D point clouds for visualization
    original_pcd = o3d.geometry.PointCloud()
    original_pcd.points = o3d.utility.Vector3dVector(original_points)
    original_pcd.paint_uniform_color([0.5, 0.5, 0.5])  # Gray

    # Create colored point clouds for each plane
    colors = [
        [1, 0, 0],  # Red
        [0, 1, 0],  # Green
        [0, 0, 1],  # Blue
        [1, 1, 0],  # Yellow
        [1, 0, 1],  # Magenta
        [0, 1, 1],  # Cyan
        [0.5, 0.5, 0],  # Olive
        [0.5, 0, 0.5],  # Purple
        [0, 0.5, 0.5],  # Teal
        [0.7, 0.3, 0.3],  # Brown
    ]

    plane_pcds = []
    for i, points in enumerate(plane_points):
        if len(points) == 0:
            continue
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.paint_uniform_color(colors[i % len(colors)])
        plane_pcds.append(pcd)

    # Create remaining points cloud if provided
    remaining_pcds = []
    if remaining_points is not None and len(remaining_points) > 0:
        remaining_pcd = o3d.geometry.PointCloud()
        remaining_pcd.points = o3d.utility.Vector3dVector(remaining_points)
        remaining_pcd.paint_uniform_color([0, 0, 0])  # Black
        remaining_pcds = [remaining_pcd]

    # Visualize
    o3d.visualization.draw_geometries([original_pcd], window_name="Original Point Cloud")
    o3d.visualization.draw_geometries(plane_pcds + remaining_pcds, window_name="Segmented Planes")


def visualize_mesh(mesh_file):
    """Visualize a mesh file."""
    print(f"Visualizing mesh: {mesh_file}")
    mesh = o3d.io.read_triangle_mesh(mesh_file)
    o3d.visualization.draw_geometries([mesh], mesh_show_back_face=True)


def compare_meshes(original_file, smoothed_file):
    """Compare original and smoothed meshes visually."""
    print(f"Comparing meshes:\n  Original: {original_file}\n  Smoothed: {smoothed_file}")

    original_mesh = o3d.io.read_triangle_mesh(original_file)
    smoothed_mesh = o3d.io.read_triangle_mesh(smoothed_file)

    # Add wireframe to original mesh to distinguish it
    original_mesh.compute_vertex_normals()
    original_mesh.paint_uniform_color([1, 0.7, 0.7])  # Light red

    smoothed_mesh.compute_vertex_normals()
    smoothed_mesh.paint_uniform_color([0.7, 0.7, 1])  # Light blue

    # Visualize both meshes
    o3d.visualization.draw_geometries(
        [original_mesh, smoothed_mesh],
        mesh_show_back_face=True,
        window_name="Mesh Comparison (Original=Red, Smoothed=Blue)"
    )


def main():
    parser = argparse.ArgumentParser(description="Complete 3D mesh processing workflow")

    # Input/output options
    parser.add_argument("--input_pcd", help="Path to input point cloud file", default="/Users/sanky/Work/catapult_hackathon/magic_mirror/output.pcd")
    parser.add_argument("--output_dir", help="Directory for output files", default="./output")
    parser.add_argument("--visualize", action="store_true", help="Visualize results at each step")

    # Point cloud processing options
    parser.add_argument("--voxel_size", type=float, default=0.01, help="Voxel size for downsampling")
    parser.add_argument("--outlier_neighbors", type=int, default=20, help="Neighbors for outlier removal")
    parser.add_argument("--outlier_std", type=float, default=2.0, help="Std ratio for outlier removal")

    # Meshing options
    parser.add_argument("--mesh_method", choices=["ball_pivoting", "poisson"], default="ball_pivoting",
                        help="Method for creating mesh from point cloud")
    parser.add_argument("--poisson_depth", type=int, default=9, help="Depth for Poisson reconstruction")

    # RANSAC smoothing options
    parser.add_argument("--min_distance", type=float, default=0.002,
                        help="Minimum threshold for high-curvature areas")
    parser.add_argument("--max_distance", type=float, default=0.01,
                        help="Maximum threshold for flat areas")
    parser.add_argument("--feature_sensitivity", type=float, default=2.0,
                        help="Feature sensitivity (higher preserves more details)")

    # STL conversion options
    parser.add_argument("--laplacian_smooth", action="store_true",
                        help="Apply Laplacian smoothing during STL conversion")
    parser.add_argument("--smooth_iterations", type=int, default=10,
                        help="Iterations for Laplacian smoothing")

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Define file paths
    initial_mesh_file = os.path.join(args.output_dir, "initial_mesh.off")
    ransac_smoothed_file = os.path.join(args.output_dir, "ransac_smoothed.off")
    final_stl_file = os.path.join(args.output_dir, "final_model.stl")

    print("=" * 80)
    print("Starting 3D Mesh Processing Workflow")
    print("=" * 80)

    # Step 1: Process point cloud
    pcd = process_point_cloud(
        input_pcd_path=args.input_pcd,
        voxel_size=args.voxel_size,
        outlier_nb_neighbors=args.outlier_neighbors,
        outlier_std_ratio=args.outlier_std
    )

    if args.visualize:
        print("Visualizing processed point cloud")
        o3d.visualization.draw_geometries([pcd], window_name="Processed Point Cloud")

    # Step 2: Create initial mesh
    mesh = create_mesh_from_point_cloud(
        pcd,
        method=args.mesh_method,
        poisson_depth=args.poisson_depth
    )

    # Save initial mesh
    print(f"Saving initial mesh to {initial_mesh_file}")
    o3d.io.write_triangle_mesh(initial_mesh_file, mesh)

    if args.visualize:
        print("Visualizing initial mesh")
        o3d.visualization.draw_geometries([mesh], mesh_show_back_face=True, window_name="Initial Mesh")

    # Step 3: Apply RANSAC-based adaptive smoothing
    smoothed_mesh = smooth_mesh_ransac(
        initial_mesh_file,
        ransac_smoothed_file,
        min_distance=args.min_distance,
        max_distance=args.max_distance,
        feature_sensitivity=args.feature_sensitivity,
        visualize=args.visualize
    )

    if args.visualize:
        print("Visualizing RANSAC smoothed mesh")
        visualize_mesh(ransac_smoothed_file)

    # Step 4: Convert to STL with optional Laplacian smoothing
    final_mesh = convert_to_stl(
        ransac_smoothed_file,
        final_stl_file,
        smooth=args.laplacian_smooth,
        iterations=args.smooth_iterations
    )

    if args.visualize:
        print("Visualizing final STL mesh")
        visualize_mesh(final_stl_file)

        # Compare original and final meshes
        compare_meshes(initial_mesh_file, final_stl_file)

    print("=" * 80)
    print("Workflow Complete!")
    print(f"Final STL file saved to: {final_stl_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()