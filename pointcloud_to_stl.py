import open3d as o3d
import numpy as np
import trimesh
import pymeshlab as ml
from meshlib import mrmeshpy
from tqdm import tqdm

dataset = o3d.data.OfficePointClouds()
pcds = []
for pcd_path in dataset.paths:
    pcds.append(o3d.io.read_point_cloud(pcd_path))

selected_pcd = pcds[13]
# selected_pcd = o3d.io.read_point_cloud("output.pcd")
# selected_pcd = selected_pcd.voxel_down_sample(voxel_size=0.01)
selected_pcd, _ = selected_pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
selected_pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(
    radius=0.1, max_nn=50))  # increase radius
selected_pcd.orient_normals_consistent_tangent_plane(100)
o3d.visualization.draw_geometries([selected_pcd], mesh_show_back_face=True)


distances = selected_pcd.compute_nearest_neighbor_distance()
avg_dist = sum(distances) / len(distances)
radii = [avg_dist * x for x in [0.5, 1.0, 2.0]]

mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
selected_pcd, o3d.utility.DoubleVector(radii))

# pcd_tree = o3d.geometry.KDTreeFlann(selected_pcd)
# mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(selected_pcd, depth=10)[0]
mesh.remove_duplicated_vertices()
mesh.remove_degenerate_triangles()
mesh.remove_unreferenced_vertices()
mesh.remove_non_manifold_edges()

o3d.visualization.draw_geometries([mesh], mesh_show_back_face=True)

o3d.io.write_triangle_mesh("output_mesh.off", mesh)

import ransac_smoothen_off
input_file = "output_mesh.off"  # Replace with your .OFF file path
output_file = "smoothed_ransac_4.off"
output_dir = "./"  # Directory for comparison images

# Parameters to adjust
min_distance = 0.002  # Minimum distance threshold for high-curvature areas
max_distance = 0.01  # Maximum distance threshold for flat areas
feature_sensitivity = 2.0  # Higher values preserve more features

# Process the mesh
smoothed_mesh = ransac_smoothen_off.smooth_off_file(
    input_file,
    output_file,
    min_distance=min_distance,
    max_distance=max_distance,
    feature_sensitivity=feature_sensitivity,
    visualize=True
)

import o3d_off_to_stl
o3d_off_to_stl.convert_off_to_stl("smoothed_ransac_4.off", "output.stl")

mesh = o3d.io.read_triangle_mesh("output.stl")
o3d.visualization.draw_geometries([mesh], mesh_show_back_face=True)

import visualize_and_compare_off_files
input_file = "smoothed_ransac_4.off"
visualize_and_compare_off_files.visualize_off_file(input_file)