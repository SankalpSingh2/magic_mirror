import * as THREE from 'three';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { GUI } from 'three/addons/libs/lil-gui.module.min.js';

let scene, camera, renderer, controls, clock;
let gltfScene = null;
let axesHelper = null;
let ambientLight, directionalLight;

const gltfSettings = {
  autoRotate: false,
  showAxes: false,
  ambientIntensity: 0.5,
  directionalIntensity: 0.8,
  directionalColor: "#ffffff"
};

init();
animate();

function init() {
  const container = document.getElementById('glb-preview-container');
  if (!container) {
    console.error("GLTF/GLB preview container not found.");
    return;
  }
  
  // Scene setup
  scene = new THREE.Scene();
  
  // Camera setup
  camera = new THREE.PerspectiveCamera(
    75,
    container.clientWidth / container.clientHeight,
    0.1,
    1000
  );
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  scene.add(camera);
  
  clock = new THREE.Clock();
  
  // Renderer setup
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);
  
  // Controls setup
  controls = new TrackballControls(camera, renderer.domElement);
  controls.rotateSpeed = 2.0;
  controls.zoomSpeed = 1.2;
  controls.panSpeed = 0.3;
  controls.dynamicDampingFactor = 0.2;
  
  // Lighting
  ambientLight = new THREE.AmbientLight(0xffffff, gltfSettings.ambientIntensity);
  scene.add(ambientLight);
  
  directionalLight = new THREE.DirectionalLight(new THREE.Color(gltfSettings.directionalColor), gltfSettings.directionalIntensity);
  directionalLight.position.set(20, 20, 20);
  scene.add(directionalLight);
  
  // Load glTF file
  const loader = new GLTFLoader();
  loader.load(
    '/output',
    (gltf) => {
      gltfScene = gltf.scene;

      // Center the model
      const box = new THREE.Box3().setFromObject(gltfScene);
      const center = box.getCenter(new THREE.Vector3());
      gltfScene.position.sub(center);

      scene.add(gltfScene);
      
      // Add AxesHelper to glTF scene so it rotates with the model.
      axesHelper = new THREE.AxesHelper(5);
      axesHelper.visible = gltfSettings.showAxes;
      gltfScene.add(axesHelper);

      render();
    },
    (xhr) => {
      console.log(Math.round((xhr.loaded / xhr.total) * 100) + '% loaded');
    },
    (error) => {
      console.error('Error loading glTF file:', error);
    }
  );
  
  // GUI controls
  const gui = new GUI({ container: container });
  gui.domElement.style.position = 'absolute';
  gui.domElement.style.top = '0px';
  gui.domElement.style.left = '0px';
  
  gui.add(gltfSettings, 'autoRotate').name('Auto Rotate').onChange(render);
  gui.add(gltfSettings, 'showAxes').name('Show Axes').onChange((value) => {
    if (axesHelper) {
      axesHelper.visible = value;
      render();
    }
  });
  
  // Lighting controls
  gui.add(gltfSettings, 'ambientIntensity', 0, 2).name('Ambient Intensity').onChange((value) => {
    if (ambientLight) {
      ambientLight.intensity = value;
      render();
    }
  });
  gui.add(gltfSettings, 'directionalIntensity', 0, 2).name('Directional Intensity').onChange((value) => {
    if (directionalLight) {
      directionalLight.intensity = value;
      render();
    }
  });
  gui.addColor(gltfSettings, 'directionalColor').name('Directional Color').onChange((value) => {
    if (directionalLight) {
      directionalLight.color.set(value);
      render();
    }
  });
  gui.open();
  
  // Fullscreen button
  const fsButton = document.getElementById('fullscreen-button-glb');
  if (fsButton) {
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
  const container = document.getElementById('glb-preview-container');
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
  
  if (gltfScene && gltfSettings.autoRotate) {
    gltfScene.rotation.x += delta * 0.2;
    gltfScene.rotation.y += delta * 0.5;
  }
  
  render();
}

function render() {
  renderer.render(scene, camera);
}
