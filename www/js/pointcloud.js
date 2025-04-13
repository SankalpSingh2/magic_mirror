import * as THREE from 'three';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { XYZLoader } from 'three/addons/loaders/XYZLoader.js';
import { GUI } from 'three/addons/libs/lil-gui.module.min.js';

let camera, scene, renderer, clock, controls;
let points;
let material;
let axesHelper;

const settings = { 
  autoRotate: false,
  showAxes: false
};

init();
animate();

function init() {
    const container = document.getElementById('pointcloud-container');

    // Set up the renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    // Create the scene
    scene = new THREE.Scene();

    // Do not add axes to scene directly anymore.
    // We'll attach it to the points so it rotates together.
    axesHelper = new THREE.AxesHelper(5);
    axesHelper.visible = settings.showAxes; // Initial state from GUI

    // Set up the camera (similar to the XYZ example)
    camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 100);
    camera.position.set(5, 3, 5);
    scene.add(camera);
    camera.lookAt(scene.position);

    // Create a clock for animations
    clock = new THREE.Clock();

    // Set up TrackballControls for freeform navigation
    controls = new TrackballControls(camera, renderer.domElement);
    controls.addEventListener('change', render);
    controls.rotateSpeed = 2.0;
    controls.zoomSpeed = 1.2;
    controls.panSpeed = 0.3;
    controls.dynamicDampingFactor = 0.2;

    // Create the PointsMaterial once, so that GUI controls affect it
    material = new THREE.PointsMaterial({ size: 0.01, color: 0xffffff });

    // Set up the GUI controls in the top left of the container
    const gui = new GUI({ container: container });
    gui.domElement.style.position = 'absolute';
    gui.domElement.style.top = '0px';
    gui.domElement.style.left = '0px';
    gui.add(material, 'size', 0.001, 0.5).name('Point Size').onChange(render);
    gui.addColor(material, 'color').name('Point Color').onChange(render);
    gui.add(settings, 'autoRotate').name('Auto Rotate').onChange(render);
    // Instead of binding directly to axesHelper.visible (which now is a child of points)
    // we use the settings toggle and then update axesHelper visibility:
    gui.add(settings, 'showAxes').name('Show Axes').onChange((value) => {
        axesHelper.visible = value;
        render();
    });
    gui.open();

    // Begin updating the point cloud immediately and then every second
    updatePointCloud();
    setInterval(updatePointCloud, 1000);

    window.addEventListener('resize', onWindowResize);

    // Set up the fullscreen button functionality
    const fsButton = document.getElementById('fullscreen-button-xyz');
    fsButton.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            container.requestFullscreen().catch(err => {
                console.error(`Error enabling fullscreen mode: ${err.message} (${err.name})`);
            });
            fsButton.textContent = 'Exit Fullscreen';
        } else {
            document.exitFullscreen();
            fsButton.textContent = 'Fullscreen';
        }
    });
    document.addEventListener('fullscreenchange', () => {
        if (!document.fullscreenElement) {
            fsButton.textContent = 'Fullscreen';
        }
    });
}

// This function loads the updated XYZ file and replaces the current point cloud,
// preserving its rotation. It also attaches the axesHelper as a child of the points so
// the axis rotates together with the model.
function updatePointCloud() {
    const loader = new XYZLoader();
    loader.load(
        '/pointcloud.xyz',
        function (geometry) {
            geometry.center();
            // Save previous rotation if points already exist
            let previousRotation = new THREE.Euler();
            if (points) {
                previousRotation.copy(points.rotation);
                scene.remove(points);
            }
            // Create new Points object with the loaded geometry and existing material
            points = new THREE.Points(geometry, material);
            points.rotation.copy(previousRotation);
            // Attach axesHelper as a child of the points so it follows the rotation
            points.add(axesHelper);
            scene.add(points);
            render();
        },
        undefined,
        function (error) {
            console.error('Error loading XYZ file:', error);
        }
    );
}

function onWindowResize() {
    const container = document.getElementById('pointcloud-container');
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
    controls.handleResize();
    render();
}

function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();

    // Update TrackballControls for damping and user interaction
    if (controls) controls.update();

    // If autoRotate is enabled, slowly rotate the point cloud (axesHelper rotates with it)
    if (points && settings.autoRotate) {
        points.rotation.x += delta * 0.2;
        points.rotation.y += delta * 0.5;
    }

    render();
}

function render() {
    renderer.render(scene, camera);
}
