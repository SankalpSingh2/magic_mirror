import * as THREE from 'three';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { GUI } from 'three/addons/libs/lil-gui.module.min.js';

let scene, camera, renderer, controls, clock;
let stlMesh = null;
let axesHelper = null;
let stlMaterial = null; // Global material reference for the STL mesh
let ambientLight, directionalLight;  // Global light references

// Update settings: add a color property for the mesh, and options for ambient/directional lights
const stlSettings = {
  autoRotate: false,
  showAxes: false,
  color: 0xffffff,
  ambientIntensity: 0.5,
  directionalIntensity: 0.8,
  directionalColor: "#ffffff"
};

init();
animate();

function init() {
  const container = document.getElementById('stl-preview-container');
  if (!container) {
    console.error("STL preview container not found.");
    return;
  }
  
  // Create scene
  scene = new THREE.Scene();
  
  // Set up camera
  camera = new THREE.PerspectiveCamera(
    75,
    container.clientWidth / container.clientHeight,
    0.1,
    1000
  );
  camera.position.set(0, 0, 50);
  camera.lookAt(0, 0, 0);
  scene.add(camera);
  
  // Create a clock for delta timing
  clock = new THREE.Clock();
  
  // Set up renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);
  
  // Set up TrackballControls for freeform navigation
  controls = new TrackballControls(camera, renderer.domElement);
  controls.rotateSpeed = 2.0;
  controls.zoomSpeed = 1.2;
  controls.panSpeed = 0.3;
  controls.dynamicDampingFactor = 0.2;
  
  // Add basic lighting using parameters from stlSettings
  ambientLight = new THREE.AmbientLight(0xffffff, stlSettings.ambientIntensity);
  scene.add(ambientLight);
  
  directionalLight = new THREE.DirectionalLight(new THREE.Color(stlSettings.directionalColor), stlSettings.directionalIntensity);
  directionalLight.position.set(20, 20, 20);
  scene.add(directionalLight);
  
  // Load the STL file from /output using STLLoader (ignore textures)
  const loader = new STLLoader();
  loader.load(
    '/output',
    (geometry) => {
      geometry.center();
      // Create MeshPhongMaterial using the current color setting from stlSettings
      stlMaterial = new THREE.MeshPhongMaterial({
        color: stlSettings.color,
      });
      stlMesh = new THREE.Mesh(geometry, stlMaterial);
      scene.add(stlMesh);
      
      // Create an AxesHelper and attach it to the STL mesh so it rotates with it.
      axesHelper = new THREE.AxesHelper(5);
      axesHelper.visible = stlSettings.showAxes;
      stlMesh.add(axesHelper);
      
      render();
    },
    (xhr) => {
      console.log(Math.round((xhr.loaded / xhr.total) * 100) + '% loaded');
    },
    (error) => {
      console.error('Error loading STL file:', error);
    }
  );
  
  // Create GUI control panel for STL preview inside the preview container
  const gui = new GUI({ container: container });
  gui.domElement.style.position = 'absolute';
  gui.domElement.style.top = '0px';
  gui.domElement.style.left = '0px';
  
  // Add color chooser similar to pointcloud.js
  gui.addColor(stlSettings, 'color').name('Mesh Color').onChange((value) => {
    if (stlMaterial) {
      stlMaterial.color.set(value);
      render();
    }
  });
  
  gui.add(stlSettings, 'autoRotate').name('Auto Rotate').onChange(render);
  gui.add(stlSettings, 'showAxes').name('Show Axes').onChange((value) => {
    if (axesHelper) {
      axesHelper.visible = value;
      render();
    }
  });
  
  // Add lighting controls:
  gui.add(stlSettings, 'ambientIntensity', 0, 2).name('Ambient Intensity').onChange((value) => {
    if (ambientLight) {
      ambientLight.intensity = value;
      render();
    }
  });
  gui.add(stlSettings, 'directionalIntensity', 0, 2).name('Directional Intensity').onChange((value) => {
    if (directionalLight) {
      directionalLight.intensity = value;
      render();
    }
  });
  gui.addColor(stlSettings, 'directionalColor').name('Directional Color').onChange((value) => {
    if (directionalLight) {
      directionalLight.color.set(value);
      render();
    }
  });
  gui.open();
  
  // Set up the STL preview fullscreen button positioned at bottom right
  const fsButton = document.getElementById('fullscreen-button-stl');
  if (fsButton) {
    fsButton.style.position = 'absolute';
    fsButton.style.bottom = '10px';
    fsButton.style.right = '10px';
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
  
  window.addEventListener('resize', onWindowResize);
}

function onWindowResize() {
  const container = document.getElementById('stl-preview-container');
  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
  controls.handleResize();
  render();
}

function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  controls.update();
  
  if (stlMesh && stlSettings.autoRotate) {
    stlMesh.rotation.x += delta * 0.2;
    stlMesh.rotation.y += delta * 0.5;
  }
  
  render();
}

function render() {
  renderer.render(scene, camera);
}
