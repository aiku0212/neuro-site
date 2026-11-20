// 3D view for a receptor card. The page loads this file only when the reader asks for 3D.
// It expects an import map that points the bare name 'three' at the vendored build.
import * as THREE from 'three';
import { GLTFLoader } from './vendor/three-r160/loaders/GLTFLoader.js';
import { OrbitControls } from './vendor/three-r160/controls/OrbitControls.js';

// host: an element with a set size.
// opts: {model, alt, reduce, labels:[{text, at:[x,y,z]}], view:{az, lo, hi, r}, slab, membraneHalf}
//   view.az is the side to start from in degrees, lo and hi are the model's lowest and highest
//   points, and r is its widest radius. slab is the width of the membrane slab.
// Model units are nanometres, +Y points out of the cell, and the origin is mid-membrane.
// Resolves to {setPaused, dispose} once the model is on screen.
export function mount(host, opts) {
  const reduce = !!opts.reduce;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const canvas = renderer.domElement;
  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-label', opts.alt);
  canvas.tabIndex = 0;
  host.appendChild(canvas);

  const scene = new THREE.Scene();
  const view = opts.view, az = view.az * Math.PI / 180;
  const target = new THREE.Vector3(0, (view.lo + view.hi) / 2, 0);
  const cam = new THREE.PerspectiveCamera(28, 1, 0.5, 600);
  // start on the side the still image was rendered from, far enough back to fit the whole model
  const from = new THREE.Vector3(Math.sin(az), 0.15, Math.cos(az)).normalize();
  function fitDistance(aspect) {
    const t = Math.tan(cam.fov * Math.PI / 360);
    // the near side of the model looks larger than its middle, so stand back by its radius as well
    return view.r + Math.max((view.hi - view.lo) / 2 / t, view.r / (t * aspect)) * 1.1;
  }
  let dist = fitDistance(0.8);
  cam.position.copy(target).addScaledVector(from, dist);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xaab4c0, 2.0));
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  cam.add(key); key.position.set(-4, 8, 6); scene.add(cam);

  // The membrane is a plain slab. Its height is estimated, not measured.
  const half = opts.membraneHalf || 1.5, wide = opts.slab || 11;
  const slab = new THREE.Mesh(
    new THREE.BoxGeometry(wide, half * 2, wide),
    new THREE.MeshBasicMaterial({ color: 0x93a6ba, transparent: true, opacity: 0.13, depthWrite: false }));
  slab.renderOrder = 2; scene.add(slab);
  const rim = new THREE.LineSegments(
    new THREE.EdgesGeometry(slab.geometry),
    new THREE.LineBasicMaterial({ color: 0x93a6ba, transparent: true, opacity: 0.55 }));
  scene.add(rim);

  const controls = new OrbitControls(cam, canvas);
  controls.target.copy(target);
  controls.enablePan = false;
  controls.minDistance = dist * 0.3; controls.maxDistance = dist * 2;
  controls.enableDamping = !reduce;
  controls.autoRotate = !reduce; controls.autoRotateSpeed = 0.9;
  controls.update();

  // labels are HTML, placed over the canvas each frame
  const layer = document.createElement('div');
  layer.className = 'rc-labels'; layer.setAttribute('aria-hidden', 'true');
  host.appendChild(layer);
  const tags = (opts.labels || []).map(function (l) {
    const el = document.createElement('span');
    el.className = 'rc-tag'; el.textContent = l.text; layer.appendChild(el);
    return { el: el, at: new THREE.Vector3(l.at[0], l.at[1], l.at[2]) };
  });
  const v = new THREE.Vector3();
  let W = 1, H = 1;
  function placeTags() {
    for (const t of tags) {
      v.copy(t.at).project(cam);
      const on = v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05;
      t.el.style.visibility = on ? 'visible' : 'hidden';
      t.el.style.transform = 'translate(' + ((v.x * 0.5 + 0.5) * W).toFixed(1) + 'px,' +
        ((-v.y * 0.5 + 0.5) * H).toFixed(1) + 'px)';
    }
  }

  function size() {
    const r = host.getBoundingClientRect();
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    renderer.setSize(W, H, false);
    canvas.style.width = '100%'; canvas.style.height = '100%';
    cam.aspect = W / H;
    cam.updateProjectionMatrix();
    // keep the whole model in view when the figure changes shape, without undoing the reader's zoom
    const want = fitDistance(cam.aspect), now = cam.position.distanceTo(controls.target);
    cam.position.sub(controls.target).multiplyScalar(now * want / dist / now).add(controls.target);
    dist = want; controls.minDistance = dist * 0.3; controls.maxDistance = dist * 2;
    controls.update(); draw();
  }
  function draw() { renderer.render(scene, cam); placeTags(); }

  // Draw only while the figure is on screen and the tab is showing.
  let seen = true, raf = 0, gone = false;
  function frame() {
    raf = 0;
    if (gone || !seen || document.hidden) return;
    controls.update(); draw();
    raf = requestAnimationFrame(frame);
  }
  function wake() { if (!raf && !gone) raf = requestAnimationFrame(frame); }
  const io = new IntersectionObserver(function (es) { seen = es[0].isIntersecting; wake(); });
  io.observe(host);
  const ro = new ResizeObserver(size); ro.observe(host);
  document.addEventListener('visibilitychange', wake);

  // Arrow keys turn the model, and plus and minus zoom. Tab moves on as usual.
  const off = new THREE.Vector3(), sph = new THREE.Spherical();
  function onKey(e) {
    const k = e.key; let used = true;
    off.copy(cam.position).sub(controls.target); sph.setFromVector3(off);
    if (k === 'ArrowLeft') sph.theta -= 0.14;
    else if (k === 'ArrowRight') sph.theta += 0.14;
    else if (k === 'ArrowUp') sph.phi = Math.max(0.25, sph.phi - 0.1);
    else if (k === 'ArrowDown') sph.phi = Math.min(Math.PI - 0.25, sph.phi + 0.1);
    else if (k === '+' || k === '=') sph.radius = Math.max(controls.minDistance, sph.radius * 0.9);
    else if (k === '-' || k === '_') sph.radius = Math.min(controls.maxDistance, sph.radius / 0.9);
    else used = false;
    if (!used) return;
    e.preventDefault();
    cam.position.copy(controls.target).add(off.setFromSpherical(sph));
    controls.update(); draw();
  }
  canvas.addEventListener('keydown', onKey);

  return new Promise(function (resolve, reject) {
    new GLTFLoader().load(opts.model, function (gltf) {
      scene.add(gltf.scene);
      size(); wake();
      resolve({
        setPaused: function (p) { controls.autoRotate = !p && !reduce; wake(); },
        dispose: function () {
          gone = true; cancelAnimationFrame(raf); io.disconnect(); ro.disconnect();
          document.removeEventListener('visibilitychange', wake);
          canvas.removeEventListener('keydown', onKey);
          controls.dispose();
          scene.traverse(function (o) {
            if (o.geometry) o.geometry.dispose();
            if (o.material) o.material.dispose();
          });
          renderer.dispose(); canvas.remove(); layer.remove();
        }
      });
    }, undefined, function (err) {
      gone = true; io.disconnect(); ro.disconnect(); controls.dispose(); renderer.dispose();
      canvas.remove(); layer.remove(); reject(err);
    });
  });
}
