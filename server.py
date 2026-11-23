"""
Smart User Presence Detection & Virtual Mouse Web Server
========================================================
Lightweight HTTP server on http://localhost:8000 with REAL-TIME,
AUTOMATIC face detection and timed presence message popups.
"""

import os
import sys
import json
import time
import ctypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.parse

PORT = 8000

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart User Presence Detection & Virtual Mouse</title>

  <!-- Google MediaPipe Face Detection for high-accuracy in-browser face tracking -->
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js" crossorigin="anonymous"></script>
  <script src="https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/face_detection.js" crossorigin="anonymous"></script>

  <style>
    :root {
      --bg: #0d0f18;
      --card-bg: #161826;
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --green: #10b981;
      --yellow: #f59e0b;
      --red: #ef4444;
      --purple: #8b5cf6;
      --pink: #ec4899;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --border: #23273c;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
    body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; overflow-x: hidden; }

    /* Top Nav */
    header {
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .logo-box { display: flex; align-items: center; gap: 12px; }
    .logo-icon {
      background: linear-gradient(135deg, #6366f1, #a855f7);
      width: 38px; height: 38px; border-radius: 10px;
      display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }
    .brand-title { font-size: 18px; font-weight: 700; }
    .brand-subtitle { font-size: 12px; color: var(--text-muted); }

    .nav-status {
      display: flex; align-items: center; gap: 10px;
      background: #11131e; padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border); font-size: 13px;
    }
    .status-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--green); transition: background 0.3s; }
    .status-dot.away { background: var(--red); box-shadow: 0 0 10px rgba(239, 68, 68, 0.6); }

    /* Main Container */
    main {
      flex: 1; padding: 24px; display: grid; grid-template-columns: 1fr 390px; gap: 24px; max-width: 1400px; margin: 0 auto; width: 100%;
    }

    /* Video Feed Card */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .card-header {
      padding: 14px 20px; border-bottom: 1px solid var(--border);
      display: flex; justify-content: space-between; align-items: center; font-size: 15px; font-weight: 600;
    }
    .video-viewport {
      position: relative; background: #000; flex: 1; min-height: 480px; display: flex; align-items: center; justify-content: center;
    }
    video#webcam { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); display: block; }
    canvas#overlayCanvas {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%; transform: scaleX(-1); pointer-events: none;
    }
    /* Hidden canvas for fast pixel analytics */
    canvas#procCanvas { display: none; }

    /* Video Overlays */
    .viewport-overlay {
      position: absolute; top: 16px; left: 16px; right: 16px; display: flex; justify-content: space-between; pointer-events: none;
    }
    .badge {
      background: rgba(15, 17, 26, 0.85); backdrop-filter: blur(8px);
      padding: 6px 14px; border-radius: 30px; font-size: 12px; font-weight: 600; border: 1px solid rgba(255, 255, 255, 0.1);
      display: flex; align-items: center; gap: 8px;
    }
    .badge-presence { transition: all 0.3s ease; }
    .badge-presence.away { border-color: var(--red); color: #fca5a5; }

    .away-banner {
      position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
      background: rgba(239, 68, 68, 0.92); backdrop-filter: blur(8px); color: white;
      padding: 10px 24px; border-radius: 30px; font-weight: 700; font-size: 13px; display: none;
      box-shadow: 0 4px 20px rgba(239, 68, 68, 0.5);
      animation: pulse 1.5s infinite;
      text-align: center;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: translateX(-50%) scale(1); }
      50% { opacity: 0.85; transform: translateX(-50%) scale(1.02); }
    }

    /* Video Toolbar */
    .video-toolbar {
      padding: 14px 20px; background: #131520; display: flex; justify-content: space-between; align-items: center;
      border-top: 1px solid var(--border);
    }
    .btn {
      background: var(--accent); color: white; border: none; padding: 8px 16px; border-radius: 8px;
      font-size: 13px; font-weight: 600; cursor: pointer; transition: 0.2s; display: inline-flex; align-items: center; gap: 8px;
    }
    .btn:hover { background: var(--accent-hover); }
    .btn-secondary { background: #23273c; color: #cdd6f4; }
    .btn-secondary:hover { background: #323753; color: white; }
    .btn-danger { background: var(--red); }
    .btn-danger:hover { background: #dc2626; }
    .btn-green { background: var(--green); }
    .btn-green:hover { background: #059669; }

    /* Side Panel */
    .sidebar { display: flex; flex-direction: column; gap: 20px; }
    .section-title { font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 12px; }

    .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
    .stat-box {
      background: #11131e; border: 1px solid var(--border); border-radius: 12px; padding: 12px;
    }
    .stat-val { font-size: 22px; font-weight: 800; color: var(--accent); }
    .stat-val.red { color: var(--red); }
    .stat-lbl { font-size: 11px; color: var(--text-muted); margin-top: 4px; }

    /* Timer Progress */
    .timer-container {
      background: #11131e; border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px;
    }
    .timer-header { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 8px; }
    .progress-bar-bg { width: 100%; height: 8px; background: #23273c; border-radius: 4px; overflow: hidden; }
    .progress-bar-fill { height: 100%; width: 0%; background: linear-gradient(90deg, var(--green), var(--yellow), var(--red)); transition: width 0.3s; }

    /* Stage triggers list */
    .stages-list { display: flex; flex-direction: column; gap: 8px; }
    .stage-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: 10px 14px; background: #11131e; border: 1px solid var(--border); border-radius: 10px; font-size: 12px;
    }
    .stage-item.triggered { border-color: var(--accent); background: #1a1d2e; }
    .stage-pill { padding: 3px 8px; border-radius: 12px; font-size: 10px; font-weight: bold; background: #23273c; color: var(--text-muted); }

    /* Sensitivity & Controls */
    .setting-row { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 12px; }
    input[type=range] { accent-color: var(--accent); cursor: pointer; }

    /* =========================================================================
       MODAL & NOTIFICATION POPUP SYSTEM (Clean Modern Card Look)
       ========================================================================= */
    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0, 0, 0, 0.72); backdrop-filter: blur(8px);
      display: none; align-items: center; justify-content: center; z-index: 9999;
    }
    .modal-backdrop.open { display: flex; }

    .popup-card {
      background: #181a26; border-radius: 16px; width: 440px; max-width: 90vw;
      border: 1px solid var(--accent); overflow: hidden; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.85);
      animation: popIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes popIn {
      0% { opacity: 0; transform: scale(0.92) translateY(20px); }
      100% { opacity: 1; transform: scale(1) translateY(0); }
    }
    .popup-accent { height: 6px; background: var(--accent); }
    .popup-body { padding: 24px; }
    .popup-header { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
    .popup-icon { font-size: 30px; }
    .popup-title { font-size: 18px; font-weight: 700; color: #fff; }
    .popup-msg { font-size: 14px; color: #d1d5db; line-height: 1.5; margin-bottom: 24px; }
    .popup-actions { display: flex; justify-content: flex-end; gap: 12px; }

    /* Welcome Back Toast */
    .toast-container {
      position: fixed; top: 24px; left: 50%; transform: translateX(-50%); z-index: 10000; pointer-events: none;
    }
    .welcome-toast {
      background: #181a26; border: 1.5px solid var(--green); border-radius: 30px;
      padding: 12px 24px; display: flex; align-items: center; gap: 14px;
      box-shadow: 0 10px 30px rgba(16, 185, 129, 0.35);
      opacity: 0; transform: translateY(-20px); transition: 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .welcome-toast.show { opacity: 1; transform: translateY(0); }
    .toast-icon { font-size: 22px; }
    .toast-text { font-size: 14px; font-weight: 600; color: #a6e3a1; }
  </style>
</head>
<body>

  <!-- Top Navigation Bar -->
  <header>
    <div class="logo-box">
      <div class="logo-icon">🖱️</div>
      <div>
        <div class="brand-title">Smart User Presence Detection System</div>
        <div class="brand-subtitle">Real-Time Automated Face Tracking & Timed Pop-ups</div>
      </div>
    </div>
    <div class="nav-status">
      <div class="status-dot" id="statusDot"></div>
      <span id="navStatusText">Initializing Face Detector...</span>
    </div>
  </header>

  <!-- Welcome Back Toast -->
  <div class="toast-container">
    <div class="welcome-toast" id="welcomeToast">
      <span class="toast-icon">🎉</span>
      <span class="toast-text" id="welcomeToastText">Welcome back! Your virtual mouse is ready!</span>
    </div>
  </div>

  <!-- Main Grid -->
  <main>
    <!-- Left: Live Camera Viewport -->
    <div class="card">
      <div class="card-header">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span>Live Webcam Feed</span>
          <span style="font-size: 11px; padding: 2px 8px; border-radius: 12px; background: #23273c; color: #818cf8;" id="engineBadge">
            Detection: Loading...
          </span>
        </div>
        <span style="font-size: 12px; color: var(--text-muted);" id="resolutionText">640x480</span>
      </div>

      <div class="video-viewport">
        <video id="webcam" autoplay playsinline muted></video>
        <canvas id="overlayCanvas"></canvas>
        <canvas id="procCanvas"></canvas>

        <!-- Live Badges -->
        <div class="viewport-overlay">
          <div class="badge badge-presence" id="presenceBadge">
            <span style="color: var(--green);" id="badgeDot">●</span>
            <span id="badgeText">Detecting Face...</span>
          </div>
          <div class="badge">
            <span>FPS: <strong id="fpsVal">--</strong></span>
          </div>
        </div>

        <!-- Banner shown during absence -->
        <div class="away-banner" id="awayBanner">
          ⚠️ USER ABSENT — VIRTUAL MOUSE PAUSED (<span id="bannerAwaySec">0</span>s)
        </div>
      </div>

      <div class="video-toolbar">
        <div style="display: flex; gap: 10px;">
          <button class="btn btn-secondary" id="toggleCamBtn" onclick="toggleCamera()">📷 Stop Camera</button>
          <button class="btn btn-secondary" onclick="simulatePresenceToggle()">🔄 Toggle Face Simulation</button>
        </div>
        <div style="font-size: 12px; color: var(--text-muted);">
          Debounce: 1.5s grace period protects against temporary glances/flickers
        </div>
      </div>
    </div>

    <!-- Right: Status & Automated Analytics -->
    <div class="sidebar">
      <div class="card" style="padding: 20px;">
        <div class="section-title">Automated Presence Analytics</div>
        <div class="stat-grid">
          <div class="stat-box">
            <div class="stat-val" id="awayTimerVal">0s</div>
            <div class="stat-lbl">Continuous Absence</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" id="confidenceVal">--%</div>
            <div class="stat-lbl">Face Confidence</div>
          </div>
        </div>

        <div class="timer-container">
          <div class="timer-header">
            <span>Next Popup In:</span>
            <strong id="nextThresholdText">10s (User Present)</strong>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" id="timerFill"></div>
          </div>
        </div>

        <!-- Notification Stages Checklist -->
        <div class="section-title">Scheduled Absence Stages</div>
        <div class="stages-list">
          <div class="stage-item" id="stage10">
            <div><strong>10 Seconds</strong>: Are you still there?</div>
            <div class="stage-pill" id="pill10">Pending</div>
          </div>
          <div class="stage-item" id="stage30">
            <div><strong>30 Seconds</strong>: Where did you go?</div>
            <div class="stage-pill" id="pill30">Pending</div>
          </div>
          <div class="stage-item" id="stage60">
            <div><strong>1 Minute</strong>: Mouse waiting for you!</div>
            <div class="stage-pill" id="pill60">Pending</div>
          </div>
          <div class="stage-item" id="stage180">
            <div><strong>3 Minutes</strong>: Lock screen action</div>
            <div class="stage-pill" id="pill180">Pending</div>
          </div>
        </div>

        <!-- Detection Sensitivity Slider -->
        <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border);">
          <div class="setting-row">
            <span>Detection Sensitivity</span>
            <span id="sensText">Normal (50%)</span>
          </div>
          <input type="range" id="sensRange" min="20" max="80" value="50" style="width: 100%; margin-top: 6px;"
                 oninput="onSensitivityChange(this.value)">
        </div>
      </div>

      <!-- Quick Test Simulation Panel -->
      <div class="card" style="padding: 20px;">
        <div class="section-title">Manual Override & Tests</div>
        <p style="font-size: 11px; color: var(--text-muted); margin-bottom: 12px;">
          The system detects your face <strong>automatically</strong>. You can also trigger stages manually below:
        </p>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <button class="btn btn-secondary" onclick="forceTriggerStage(10)">Test 10s</button>
            <button class="btn btn-secondary" onclick="forceTriggerStage(30)">Test 30s</button>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <button class="btn btn-secondary" onclick="forceTriggerStage(60)">Test 1m</button>
            <button class="btn btn-secondary" onclick="forceTriggerStage(180)">Test 3m Lock</button>
          </div>
          <button class="btn btn-green" onclick="testWelcomeToast()">🎉 Test Welcome Toast</button>
          <button class="btn btn-danger" onclick="triggerCameraDisconnect()">⚠️ Test Camera Disconnect</button>
        </div>
      </div>
    </div>
  </main>

  <!-- POPUP MODAL -->
  <div class="modal-backdrop" id="modalBackdrop">
    <div class="popup-card" id="popupCard">
      <div class="popup-accent" id="popupAccent"></div>
      <div class="popup-body">
        <div class="popup-header">
          <span class="popup-icon" id="popupIcon">👀</span>
          <div class="popup-title" id="popupTitle">Hey, are you still there?</div>
        </div>
        <div class="popup-msg" id="popupMsg">We can't see you!</div>
        <div class="popup-actions" id="popupActions">
          <button class="btn btn-secondary" onclick="closePopup()">Dismiss</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    // =========================================================================
    // Core Elements & State
    // =========================================================================
    const video = document.getElementById('webcam');
    const overlay = document.getElementById('overlayCanvas');
    const ctx = overlay.getContext('2d');
    const procCanvas = document.getElementById('procCanvas');
    const procCtx = procCanvas.getContext('2d', { willReadFrequently: true });

    let stream = null;
    let cameraActive = true;

    // Detection state
    let faceCurrentlyDetected = false;
    let faceConfidence = 0;
    let lastFaceSeenTimestamp = Date.now();
    let isUserDeclaredAway = false;
    let awayDurationSeconds = 0;
    let activeModalStage = null;

    // Debounce grace period (1.5 seconds)
    const DEBOUNCE_MS = 1500;

    // Triggered stages tracker
    const triggeredStages = new Set();

    // Stage Definitions
    const STAGES = {
      10: { icon: "👀", title: "Hey, are you still there?", msg: "Hey, are you still there? We can't see you!", color: "#6366f1" },
      30: { icon: "☕", title: "Where did you go?", msg: "Where did you go? Take your time!", color: "#8b5cf6" },
      60: { icon: "⏳", title: "Still away?", msg: "Still away? Your virtual mouse is waiting for you!", color: "#ec4899" },
      180: { icon: "🔒", title: "Extended Absence Alert", msg: "You've been away for a while. Would you like to lock your screen?", color: "#ef4444", lock: true }
    };

    let detectionSensitivity = 0.5;
    let activeEngine = "Initializing...";
    let mpDetector = null;
    let nativeFaceDetector = null;
    let simulationOverride = null; // null = use real detection; true/false = manual force

    // Sound chime synthesizer via Web Audio API
    function playChime(freq = 587.33, type = "sine") {
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.4);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.4);
      } catch (e) {}
    }

    // =========================================================================
    // Multi-Engine Face Detection Initialization
    // =========================================================================
    async function initFaceEngines() {
      // 1. Check Native Chrome/Edge FaceDetector API
      if ('FaceDetector' in window) {
        try {
          nativeFaceDetector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 2 });
          activeEngine = "Native GPU Vision";
        } catch (e) {}
      }

      // 2. Check MediaPipe Face Detection
      if (window.FaceDetection) {
        try {
          mpDetector = new FaceDetection({
            locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`
          });
          mpDetector.setOptions({
            model: 'short',
            minDetectionConfidence: 0.5
          });
          mpDetector.onResults(onMediaPipeResults);
          activeEngine = "MediaPipe Neural Vision";
        } catch (err) {
          console.warn("MediaPipe init fallback:", err);
          if (!nativeFaceDetector) activeEngine = "Biometric Skin & Geometry Vision";
        }
      } else if (!nativeFaceDetector) {
        activeEngine = "Biometric Skin & Geometry Vision";
      }

      document.getElementById('engineBadge').textContent = `Engine: ${activeEngine}`;
    }

    // MediaPipe Results Callback
    let mpLastDetection = null;
    function onMediaPipeResults(results) {
      if (results && results.detections && results.detections.length > 0) {
        mpLastDetection = {
          found: true,
          confidence: Math.round(results.detections[0].score[0] * 100),
          box: results.detections[0].boundingBox
        };
      } else {
        mpLastDetection = { found: false, confidence: 0 };
      }
    }

    // =========================================================================
    // Webcam Capture Setup
    // =========================================================================
    async function startCamera() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
          audio: false
        });
        video.srcObject = stream;
        video.onloadedmetadata = () => {
          overlay.width = video.videoWidth;
          overlay.height = video.videoHeight;
          procCanvas.width = 160;
          procCanvas.height = 120;
          document.getElementById('resolutionText').textContent = `${video.videoWidth}x${video.videoHeight}`;
          document.getElementById('navStatusText').textContent = "Camera Live — Automated Face Tracking Active";
          cameraActive = true;
          requestAnimationFrame(masterLoop);
        };
      } catch (err) {
        console.error("Camera access error:", err);
        triggerCameraDisconnect();
      }
    }

    function toggleCamera() {
      if (cameraActive && stream) {
        stream.getTracks().forEach(t => t.stop());
        video.srcObject = null;
        cameraActive = false;
        document.getElementById('toggleCamBtn').textContent = "📷 Start Camera";
        document.getElementById('navStatusText').textContent = "Camera Paused";
      } else {
        startCamera();
        document.getElementById('toggleCamBtn').textContent = "📷 Stop Camera";
      }
    }

    // =========================================================================
    // Built-in Pure JavaScript Biometric Skin & Facial Geometry Detector
    // (Zero-dependency fallback: runs in any browser under all conditions)
    // =========================================================================
    function analyzeBiometricFace(w, h) {
      procCtx.drawImage(video, 0, 0, 160, 120);
      const imgData = procCtx.getImageData(0, 0, 160, 120);
      const data = imgData.data;

      let skinPixels = 0;
      let minX = 160, maxX = 0, minY = 120, maxY = 0;
      let totalLuma = 0;

      // Focus primarily on central 70% where sitting user is positioned
      const xStart = 20, xEnd = 140, yStart = 15, yEnd = 105;

      for (let y = yStart; y < yEnd; y++) {
        for (let x = xStart; x < xEnd; x++) {
          const idx = (y * 160 + x) * 4;
          const r = data[idx];
          const g = data[idx + 1];
          const b = data[idx + 2];

          // YCbCr skin chrominance model
          const yVal = 0.299 * r + 0.587 * g + 0.114 * b;
          const cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b;
          const cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b;

          totalLuma += yVal;

          // Standard Kovac/Chai skin cluster conditions
          if (cb >= 77 && cb <= 127 && cr >= 133 && cr <= 173 && r > g && r > b && (r - g) > 15) {
            skinPixels++;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }

      const clusterW = maxX > minX ? (maxX - minX) : 0;
      const clusterH = maxY > minY ? (maxY - minY) : 0;
      const aspect = clusterH > 0 ? (clusterW / clusterH) : 0;

      // Dynamic threshold based on sensitivity
      const minPixelsRequired = Math.round(550 * (1.1 - detectionSensitivity));

      // Face candidate must satisfy cluster size, density, and roughly 0.5 - 1.5 aspect ratio
      if (skinPixels >= minPixelsRequired && aspect >= 0.45 && aspect <= 1.6) {
        const conf = Math.min(96, Math.round((skinPixels / 1500) * 100));
        // Map bounding box to full resolution
        const scaleX = w / 160;
        const scaleY = h / 120;
        return {
          found: true,
          confidence: conf,
          box: {
            x: minX * scaleX,
            y: minY * scaleY,
            width: clusterW * scaleX,
            height: clusterH * scaleY
          }
        };
      }
      return { found: false, confidence: 0 };
    }

    // =========================================================================
    // Master Video & Automated Presence State Machine Loop
    // =========================================================================
    let lastFrameTime = performance.now();
    let frameCount = 0;
    let fps = 30;

    async function masterLoop(timestamp) {
      if (!cameraActive) return;

      frameCount++;
      if (timestamp - lastFrameTime >= 1000) {
        fps = frameCount;
        document.getElementById('fpsVal').textContent = fps;
        frameCount = 0;
        lastFrameTime = timestamp;
      }

      ctx.clearRect(0, 0, overlay.width, overlay.height);

      let isFaceFound = false;
      let detectedBox = null;
      let confScore = 0;

      // Check simulation override if user manually pressed toggle
      if (simulationOverride !== null) {
        isFaceFound = simulationOverride;
        confScore = isFaceFound ? 95 : 0;
      } else {
        // --- 1. Run MediaPipe if available ---
        if (mpDetector && video.readyState >= 2) {
          try {
            await mpDetector.send({ image: video });
            if (mpLastDetection && mpLastDetection.found) {
              isFaceFound = true;
              confScore = mpLastDetection.confidence;
              const bb = mpLastDetection.box;
              detectedBox = {
                x: bb.xCenter * overlay.width - (bb.width * overlay.width) / 2,
                y: bb.yCenter * overlay.height - (bb.height * overlay.height) / 2,
                width: bb.width * overlay.width,
                height: bb.height * overlay.height
              };
            }
          } catch (e) {}
        }

        // --- 2. Run Native FaceDetector if MediaPipe missed or not loaded ---
        if (!isFaceFound && nativeFaceDetector && video.readyState >= 2) {
          try {
            const faces = await nativeFaceDetector.detect(video);
            if (faces && faces.length > 0) {
              isFaceFound = true;
              confScore = 92;
              const b = faces[0].boundingBox;
              detectedBox = { x: b.x, y: b.y, width: b.width, height: b.height };
            }
          } catch (e) {}
        }

        // --- 3. Run Built-in Biometric Vision if still not found ---
        if (!isFaceFound && video.readyState >= 2) {
          const bioResult = analyzeBiometricFace(overlay.width, overlay.height);
          if (bioResult.found) {
            isFaceFound = true;
            confScore = bioResult.confidence;
            detectedBox = bioResult.box;
          }
        }
      }

      const now = Date.now();
      document.getElementById('confidenceVal').textContent = isFaceFound ? `${confScore}%` : `0%`;

      // -----------------------------------------------------------------------
      // AUTOMATED USER PRESENCE STATE MACHINE
      // -----------------------------------------------------------------------
      if (isFaceFound) {
        // Face is present right now
        lastFaceSeenTimestamp = now;

        // Draw animated target box on user face
        if (detectedBox) {
          drawFaceBox(detectedBox.x, detectedBox.y, detectedBox.width, detectedBox.height);
        } else {
          // Draw default center tracking indicator
          const bw = overlay.width * 0.35, bh = overlay.height * 0.48;
          drawFaceBox((overlay.width - bw) / 2, (overlay.height - bh) / 2.2, bw, bh);
        }

        // IF USER WAS PREVIOUSLY CONFIRMED AWAY: Trigger Welcome Back!
        if (isUserDeclaredAway) {
          console.log("[PRESENCE] Face re-detected! User returned.");
          isUserDeclaredAway = false;
          awayDurationSeconds = 0;
          triggeredStages.clear();

          // 1. Automatically dismiss any active absence popup!
          closePopup();

          // 2. Automatically display the Welcome Back notification toast
          showWelcomeBackToast();

          // 3. Reset stages UI
          resetStagesChecklist();
        }

        // Update UI badges for Present state
        document.getElementById('badgeDot').style.color = "var(--green)";
        document.getElementById('badgeText').textContent = "User Present (Face Active)";
        document.getElementById('presenceBadge').className = "badge badge-presence";
        document.getElementById('statusDot').className = "status-dot";
        document.getElementById('navStatusText').textContent = "User Present — Virtual Mouse Active";
        document.getElementById('awayBanner').style.display = "none";
        document.getElementById('awayTimerVal').textContent = "0s";
        document.getElementById('awayTimerVal').className = "stat-val";
        document.getElementById('nextThresholdText').textContent = "10s (User Present)";
        document.getElementById('timerFill').style.width = "0%";

      } else {
        // Face is NOT detected in this frame
        const timeSinceLastSeen = now - lastFaceSeenTimestamp;

        // Apply 1.5s Anti-Flicker Debounce filter
        if (timeSinceLastSeen >= DEBOUNCE_MS) {
          if (!isUserDeclaredAway) {
            isUserDeclaredAway = true;
            console.log("[PRESENCE] Anti-flicker threshold passed. User marked AWAY.");
          }

          awayDurationSeconds = Math.floor((timeSinceLastSeen - DEBOUNCE_MS) / 1000);
          const sec = awayDurationSeconds;

          // Update UI for Away state
          document.getElementById('badgeDot').style.color = "var(--red)";
          document.getElementById('badgeText').textContent = `No Face Detected (${sec}s)`;
          document.getElementById('presenceBadge').className = "badge badge-presence away";
          document.getElementById('statusDot').className = "status-dot away";
          document.getElementById('navStatusText').textContent = `User Away (${sec}s) — Virtual Mouse Paused`;
          document.getElementById('awayBanner').style.display = "block";
          document.getElementById('bannerAwaySec').textContent = sec;
          document.getElementById('awayTimerVal').textContent = `${sec}s`;
          document.getElementById('awayTimerVal').className = "stat-val red";

          // Progress bar towards max 180s tier
          const progressPct = Math.min(100, (sec / 180) * 100);
          document.getElementById('timerFill').style.width = `${progressPct}%`;

          // Update countdown display
          if (sec < 10) {
            document.getElementById('nextThresholdText').textContent = `10s Alert in ${10 - sec}s`;
          } else if (sec < 30) {
            document.getElementById('nextThresholdText').textContent = `30s Alert in ${30 - sec}s`;
          } else if (sec < 60) {
            document.getElementById('nextThresholdText').textContent = `1m Alert in ${60 - sec}s`;
          } else if (sec < 180) {
            document.getElementById('nextThresholdText').textContent = `3m Alert in ${180 - sec}s`;
          } else {
            document.getElementById('nextThresholdText').textContent = `All Tiers Triggered`;
          }

          // -------------------------------------------------------------------
          // AUTOMATIC SCHEDULED POP-UP TRIGGERS (10s, 30s, 60s, 180s)
          // -------------------------------------------------------------------
          [10, 30, 60, 180].forEach(stageThreshold => {
            if (sec >= stageThreshold && !triggeredStages.has(stageThreshold)) {
              triggeredStages.add(stageThreshold);
              console.log(`[AUTOMATIC POPUP] Triggering ${stageThreshold}s popup alert!`);
              displayAbsencePopup(stageThreshold);
            }
          });
        }
      }

      requestAnimationFrame(masterLoop);
    }

    // =========================================================================
    // UI Helpers: Canvas Bounding Box & Popups
    // =========================================================================
    function drawFaceBox(x, y, w, h) {
      // Clamping
      x = Math.max(10, Math.min(overlay.width - 50, x));
      y = Math.max(10, Math.min(overlay.height - 50, y));
      w = Math.max(40, Math.min(overlay.width - x, w));
      h = Math.max(40, Math.min(overlay.height - y, h));

      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2.5;
      ctx.strokeRect(x, y, w, h);

      // Tech corners
      const corner = 14;
      ctx.fillStyle = '#10b981';
      ctx.fillRect(x - 2, y - 2, corner, 4);
      ctx.fillRect(x - 2, y - 2, 4, corner);
      ctx.fillRect(x + w - corner + 2, y - 2, corner, 4);
      ctx.fillRect(x + w - 2, y - 2, 4, corner);
      ctx.fillRect(x - 2, y + h - 2, corner, 4);
      ctx.fillRect(x - 2, y + h - corner + 2, 4, corner);
      ctx.fillRect(x + w - corner + 2, y + h - 2, corner, 4);
      ctx.fillRect(x + w - 2, y + h - corner + 2, 4, corner);

      // Label
      ctx.font = '12px "Segoe UI", sans-serif';
      ctx.fillStyle = '#10b981';
      ctx.fillText('User Face', x, Math.max(16, y - 6));
    }

    // Displays the absence popup with in-place smooth updating
    function displayAbsencePopup(stage) {
      const data = STAGES[stage];
      if (!data) return;

      activeModalStage = stage;
      playChime(stage >= 180 ? 440 : 659.25, "triangle");

      // Update Checklist Pill
      const pill = document.getElementById(`pill${stage}`);
      if (pill) {
        pill.textContent = "Triggered";
        pill.style.background = data.color;
        pill.style.color = "#ffffff";
      }

      // Populate Modal Content
      document.getElementById('popupAccent').style.background = data.color;
      document.getElementById('popupIcon').textContent = data.icon;
      document.getElementById('popupTitle').textContent = data.title;
      document.getElementById('popupMsg').textContent = data.msg;

      let actionsHtml = `<button class="btn btn-secondary" onclick="closePopup()">Dismiss</button>`;
      if (data.lock) {
        actionsHtml = `
          <button class="btn btn-danger" onclick="lockWorkstation()">🔒 Lock Screen Now</button>
          <button class="btn btn-secondary" onclick="closePopup()">Dismiss</button>
        `;
      }
      document.getElementById('popupActions').innerHTML = actionsHtml;

      // Open Modal
      document.getElementById('modalBackdrop').classList.add('open');
    }

    // Automatically closes any active modal
    function closePopup() {
      document.getElementById('modalBackdrop').classList.remove('open');
      activeModalStage = null;
    }

    // Displays the Welcome Back Toast
    function showWelcomeBackToast() {
      playChime(880, "sine");
      const toast = document.getElementById('welcomeToast');
      toast.classList.add('show');
      setTimeout(() => {
        toast.classList.remove('show');
      }, 3500);
    }

    function resetStagesChecklist() {
      [10, 30, 60, 180].forEach(s => {
        const p = document.getElementById(`pill${s}`);
        if (p) {
          p.textContent = "Pending";
          p.style.background = "#23273c";
          p.style.color = "var(--text-muted)";
        }
      });
    }

    // Camera Disconnect Error Alert
    function triggerCameraDisconnect() {
      document.getElementById('popupAccent').style.background = "#ef4444";
      document.getElementById('popupIcon').textContent = "⚠️";
      document.getElementById('popupTitle').textContent = "Webcam Unavailable";
      document.getElementById('popupMsg').textContent = "Webcam feed was disconnected or camera device is unavailable!";
      document.getElementById('popupActions').innerHTML = `
        <button class="btn btn-secondary" onclick="closePopup()">Close Alert</button>
      `;
      document.getElementById('modalBackdrop').classList.add('open');
    }

    // Lock Windows PC Action
    async function lockWorkstation() {
      closePopup();
      try {
        await fetch('/api/lock', { method: 'POST' });
      } catch (e) {
        console.error(e);
      }
    }

    // Sensitivity Slider
    function onSensitivityChange(val) {
      detectionSensitivity = val / 100;
      document.getElementById('sensText').textContent = `${val < 40 ? 'Low' : val > 65 ? 'High' : 'Normal'} (${val}%)`;
    }

    // Manual Simulation / Overrides for Testing
    function forceTriggerStage(sec) {
      displayAbsencePopup(sec);
    }

    function testWelcomeToast() {
      closePopup();
      showWelcomeBackToast();
    }

    function simulatePresenceToggle() {
      if (simulationOverride === null) {
        simulationOverride = false; // Simulate away
      } else if (simulationOverride === false) {
        simulationOverride = true;  // Simulate present
      } else {
        simulationOverride = null;  // Return to auto camera detection
      }
      console.log("[SIMULATION OVERRIDE]:", simulationOverride === null ? "AUTOMATIC CAMERA DETECTION" : simulationOverride ? "SIMULATING PRESENT" : "SIMULATING AWAY");
    }

    // =========================================================================
    // Startup
    // =========================================================================
    window.addEventListener('DOMContentLoaded', async () => {
      await initFaceEngines();
      await startCamera();
    });
  </script>
</body>
</html>
"""


class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status = {"status": "running", "timestamp": time.time()}
            self.wfile.write(json.dumps(status).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/lock":
            try:
                ctypes.windll.user32.LockWorkStation()
            except Exception:
                try:
                    os.system("rundll32.exe user32.dll,LockWorkStation")
                except Exception:
                    pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), WebHandler)
    print(f"[INFO] Server started successfully on http://localhost:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
