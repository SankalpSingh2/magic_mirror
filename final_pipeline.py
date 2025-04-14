import open3d as o3d
import numpy as np
import trimesh
import pymeshlab as ml
from meshlib import mrmeshpy
import ransac_smoothen_off
import o3d_off_to_stl

perma_mesh = o3d.io.read_point_cloud("./www/pointcloud.xyz")

def draft_stl():
    pcd_tree = o3d.geometry.KDTreeFlann(perma_mesh)
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=7)[0]
    o3d.io.write_triangle_mesh("output_mesh.off", mesh)

def add_point_cloud_data(data):
    global counter
    global perma_mesh
    d = o3d.io.read_point_cloud(data)
    perma_mesh = perma_mesh + d
    o3d.io.write_point_cloud("./www/pointcloud.xyz", perma_mesh)
    draft_stl()


def load_point_cloud(file_path = ""):
    """Load a point cloud from a file."""
    pcd = None
    if not file_path:
        pcd = o3d.data.OfficePointClouds()
        pcds = []
        for pcd_path in pcd.paths:
            pcds.append(o3d.io.read_point_cloud(pcd_path))
        pcd = pcds[0]
    else:
        pcd = o3d.io.read_point_cloud(file_path)
    return pcd

def process_point_cloud(pcd, visualize=False, downloud=True):
    """Process the point cloud to remove noise and outliers."""
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=50))
    pcd.orient_normals_consistent_tangent_plane(100)
    if visualize:
        o3d.visualization.draw_geometries([pcd], mesh_show_back_face=True)

    if downloud:
        o3d.io.write_point_cloud("./www/pointcloud.xyz", pcd)
    return pcd

def create_mesh(pcd, visualize=False, alternative=False, clean=False, downloud=True):
    """Create a mesh from the point cloud."""
    distances = pcd.compute_nearest_neighbor_distance()
    avg_dist = sum(distances) / len(distances)
    radii = [avg_dist * x for x in [0.5, 1.0, 2.0]]

    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(pcd, o3d.utility.DoubleVector(radii))

    if alternative:
        pcd_tree = o3d.geometry.KDTreeFlann(pcd)
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=10)[0]

    if clean:
        mesh.remove_duplicated_vertices()
        mesh.remove_degenerate_triangles()
        mesh.remove_unreferenced_vertices()
        mesh.remove_non_manifold_edges()

    if visualize:
        o3d.visualization.draw_geometries([mesh], mesh_show_back_face=True)

    if downloud:
        o3d.io.write_triangle_mesh("output_mesh.off", mesh)
    return mesh

def smoothen_mesh(visualize=False):
    input_file = "output_mesh.off"  # Replace with your .OFF file path
    output_file = "smoothed_ransac_4.off"
    output_dir = "./"  # Directory for comparison images

    min_distance = 0.002  # Minimum distance threshold for high-curvature areas
    max_distance = 0.01  # Maximum distance threshold for flat areas
    feature_sensitivity = 2.0  # Higher values preserve more features

    smoothed_mesh = ransac_smoothen_off.smooth_off_file(
        input_file,
        output_file,
        min_distance=min_distance,
        max_distance=max_distance,
        feature_sensitivity=feature_sensitivity,
        visualize=visualize
    )

    if visualize:
        o3d.visualization.draw_geometries([smoothed_mesh], mesh_show_back_face=True)
    return smoothed_mesh

def output():
    o3d_off_to_stl.convert_off_to_stl("smoothed_ransac_4.off", "./output/output.stl")
    
if __name__ == "__main__":
    pcd = load_point_cloud()
    print("Loaded point cloud")
    
    pcd = process_point_cloud(pcd, visualize=False, downloud=True)
    print("Processed point cloud")
    
    mesh = create_mesh(pcd, visualize=False, alternative=False, clean=True, downloud=True)
    print("Created mesh")
    
    smoothed_mesh = smoothen_mesh(visualize=False)
    print("Smoothed mesh")
    
    output()
    print("Output generated")

