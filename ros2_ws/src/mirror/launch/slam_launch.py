import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.substitutions import PathJoinSubstitution, Command, LaunchConfiguration, FindExecutable
from launch_ros.substitutions import FindPackageShare
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    description_dir = get_package_share_directory("mirror")
    urdf = PathJoinSubstitution([description_dir, "urdf", "robot.urdf.xacro"])
    
    robot_description = Command(["xacro ", urdf])

    # robot state publisher
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[
            { "robot_description" : robot_description },
        ]
    )

    return LaunchDescription([
        robot_state_publisher,

        # =========================================================
        # RTABMAP SETUP
        # =========================================================

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('rtabmap_launch'),
                    'launch',
                    'rtabmap.launch.py'
                ])
            ]),
            launch_arguments={
                "args":"--delete_db_on_start",
                "stereo":"false",

                "depth_topic": "/camera/depth/image_rect_raw",
                "rgb_topic": "/camera/color/image_raw",
                "camera_info_topic": "/camera/color/camera_info",

                "frame_id":"base_link",
                "approx_sync":"true",
                "approx_sync_max_interval":"0.05",
                "sync_queue_size":"20",
                "topic_queue_size":"20",

                'rtabmap_viz': "true"
            }.items()
        )
    ])
