import numpy as np
import open3d as o3d
import trimesh
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN
import os
from scipy.spatial import KDTree


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
    # Compute curvature estimate for each point
    normals = np.asarray(pcd.normals)
    kdtree = o3d.geometry.KDTreeFlann(pcd)

    curvatures = np.zeros(len(points))
    importance = np.ones(len(points))

    # For each point, estimate curvature based on normal variation in neighborhood
    k = 30  # Number of neighbors to consider
    for i, point in enumerate(points):
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
    planes = []
    plane_points = []
    plane_indices = []

    # Create a copy of the point cloud instead of using clone()
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


def visualize_segmentation(original_points, plane_points, remaining_points=None):
    """Visualize the original points and segmented planes."""
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


def adaptive_project_points_to_planes(points, planes, plane_indices, importance_weights):
    """Project points to their assigned plane with adaptive smoothing based on importance."""
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

        for i, point in enumerate(points):
            if plane_assignments[i] == -1:
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


def smooth_off_file(input_file, output_file, min_distance=0.005, max_distance=0.02,
                    feature_sensitivity=1.0, visualize=True):
    """Main function to smooth an OFF file using adaptive RANSAC plane fitting."""
    # Load the OFF file
    pcd, original_mesh, points, faces, vertex_colors = load_off_file(input_file)
    print(f"Loaded mesh with {len(points)} vertices and {len(faces)} faces")

    # Compute feature importance for adaptive smoothing
    print("Computing feature importance...")
    importance_weights = compute_feature_importance(pcd, points)
    importance_weights = 1.0 + feature_sensitivity * (importance_weights - 1.0)  # Adjust sensitivity

    # Segment the point cloud into planes using adaptive RANSAC
    print("Segmenting planes...")
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
        print("Visualizing segmentation...")
        remaining_points = points[remaining_indices] if len(remaining_indices) > 0 else np.array([])
        visualize_segmentation(points, plane_points, remaining_points)

    # Project points onto nearest planes with adaptive smoothing
    print("Projecting points...")
    projected_points, plane_assignments = adaptive_project_points_to_planes(
        points, planes, plane_indices, importance_weights
    )

    # Create smoothed mesh with color transfer
    print("Creating smoothed mesh with texture transfer...")
    # smoothed_mesh = transfer_colors(original_mesh, vertex_colors, projected_points)
    smoothed_mesh = trimesh.Trimesh(vertices=projected_points, faces=original_mesh.faces)
    # Save the result
    print(f"Saving to {output_file}...")
    smoothed_mesh.export(output_file)

    return smoothed_mesh


def compare_meshes(original_mesh, smoothed_mesh, output_dir):
    """Generate comparison visualizations between original and smoothed mesh."""
    # Save screenshots
    orig_file = os.path.join(output_dir, "original.png")
    smooth_file = os.path.join(output_dir, "smoothed.png")

    # Create scene with both meshes for comparison
    scene = trimesh.Scene()

    # Clone meshes to avoid modifying originals
    original_copy = original_mesh.copy()
    smoothed_copy = smoothed_mesh.copy()

    # Make the smoothed mesh partially transparent
    if hasattr(smoothed_copy.visual, 'face_colors') and smoothed_copy.visual.face_colors is not None:
        smoothed_copy.visual.face_colors[:, 3] = 128  # 50% transparency

    # Add to scene with transformations to position side by side
    scene.add_geometry(original_copy, node_name="original")
    scene.add_geometry(smoothed_copy, node_name="smoothed", transform=np.eye(4))

    # Save combined view
    combined_file = os.path.join(output_dir, "comparison.png")
    try:
        scene.export(combined_file)
        print(f"Comparison saved to {combined_file}")
    except Exception as e:
        print(f"Could not save comparison: {e}")

    return combined_file


if __name__ == "__main__":
    # Example usage
    input_file = "../output_mesh.off"  # Replace with your .OFF file path
    output_file = "smoothed_ransac_4.off"
    output_dir = "../"  # Directory for comparison images

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Parameters to adjust
    min_distance = 0.002  # Minimum distance threshold for high-curvature areas
    max_distance = 0.01  # Maximum distance threshold for flat areas
    feature_sensitivity = 2.0  # Higher values preserve more features

    # Process the mesh
    smoothed_mesh = smooth_off_file(
        input_file,
        output_file,
        min_distance=min_distance,
        max_distance=max_distance,
        feature_sensitivity=feature_sensitivity,
        visualize=True
    )

    # Compare original and smoothed meshes
    compare_meshes(trimesh.load_mesh(input_file), smoothed_mesh, output_dir)