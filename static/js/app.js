/**
 * AeroLock Dashboard & Telemetry Controller
 * Connects to Python backend via REST & Event Stream, plays Web Audio feedback.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Web Audio Context for Sci-Fi sound effects
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  let audioCtx = null;

  function playSound(type) {
    try {
      if (!audioCtx) audioCtx = new AudioCtx();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      const now = audioCtx.currentTime;

      if (type === "click") {
        osc.type = "sine";
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.exponentialRampToValueAtTime(440, now + 0.05);
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.linearRampToValueAtTime(0.01, now + 0.05);
        osc.start(now);
        osc.stop(now + 0.05);
      } else if (type === "lock") {
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(320, now);
        osc.frequency.exponentialRampToValueAtTime(60, now + 0.4);
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.linearRampToValueAtTime(0.01, now + 0.4);
        osc.start(now);
        osc.stop(now + 0.4);
      } else if (type === "unlock") {
        osc.type = "triangle";
        osc.frequency.setValueAtTime(220, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.35);
        gain.gain.setValueAtTime(0.25, now);
        gain.gain.linearRampToValueAtTime(0.01, now + 0.35);
        osc.start(now);
        osc.stop(now + 0.35);
      }
    } catch (e) {
      console.warn("Audio playback not supported or user has not interacted.", e);
    }
  }

  // DOM Elements
  const statusIndicator = document.getElementById("system-status-indicator");
  const statusText = document.getElementById("system-status-text");
  const fpsCounter = document.getElementById("fps-counter");
  const hudGestureBadge = document.getElementById("hud-gesture-badge");
  const hudActionBadge = document.getElementById("hud-action-badge");
  const lockOverlayBanner = document.getElementById("lock-overlay-banner");
  const unlockInstructionText = document.getElementById("unlock-instruction-text");
  
  const telemAction = document.getElementById("telem-action");
  const telemGesture = document.getElementById("telem-gesture");
  const telemLockProg = document.getElementById("telem-lock-prog");
  const telemUnlockStage = document.getElementById("telem-unlock-stage");

  const btnToggleMouse = document.getElementById("btn-toggle-mouse");
  const toggleMouseText = document.getElementById("toggle-mouse-text");
  const btnLockNow = document.getElementById("btn-lock-now");
  const btnUnlockNow = document.getElementById("btn-unlock-now");
  const btnSaveSettings = document.getElementById("btn-save-settings");

  const videoFeedImg = document.getElementById("video-feed-img");
  if (videoFeedImg) {
    videoFeedImg.onerror = () => {
      setTimeout(() => {
        videoFeedImg.src = "/video_feed?t=" + Date.now();
      }, 1000);
    };
  }

  // Inputs
  const sliderSpeed = document.getElementById("slider-speed");
  const valSpeed = document.getElementById("val-speed");
  const sliderSmoothing = document.getElementById("slider-smoothing");
  const valSmoothing = document.getElementById("val-smoothing");
  const sliderPinch = document.getElementById("slider-pinch");
  const valPinch = document.getElementById("val-pinch");
  const sliderScroll = document.getElementById("slider-scroll");
  const valScroll = document.getElementById("val-scroll");
  const sliderMargin = document.getElementById("slider-margin");
  const valMargin = document.getElementById("val-margin");

  const selectCamera = document.getElementById("select-camera");
  const selectLockType = document.getElementById("select-lock-type");
  const sliderLockHold = document.getElementById("slider-lock-hold");
  const valLockHold = document.getElementById("val-lock-hold");
  const selectUnlockStep1 = document.getElementById("select-unlock-step1");
  const selectUnlockStep2 = document.getElementById("select-unlock-step2");
  const inputPin = document.getElementById("input-pin");

  let wasLocked = false;

  // Sliders input events
  sliderSpeed.addEventListener("input", (e) => valSpeed.textContent = `${e.target.value}x`);
  sliderSmoothing.addEventListener("input", (e) => valSmoothing.textContent = e.target.value);
  sliderPinch.addEventListener("input", (e) => valPinch.textContent = e.target.value);
  sliderScroll.addEventListener("input", (e) => valScroll.textContent = e.target.value);
  sliderMargin.addEventListener("input", (e) => valMargin.textContent = `${Math.round(e.target.value * 100)}%`);
  sliderLockHold.addEventListener("input", (e) => valLockHold.textContent = `${e.target.value}s`);

  // Tabs switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add("active");
    });
  });

  // Fetch initial config
  fetch("/api/config")
    .then((r) => r.json())
    .then((cfg) => {
      if (cfg.camera_id !== undefined && selectCamera) selectCamera.value = cfg.camera_id;
      if (cfg.cursor_speed) {
        sliderSpeed.value = cfg.cursor_speed;
        valSpeed.textContent = `${cfg.cursor_speed}x`;
      }
      if (cfg.smoothing) {
        sliderSmoothing.value = cfg.smoothing;
        valSmoothing.textContent = cfg.smoothing;
      }
      if (cfg.pinch_click_threshold) {
        sliderPinch.value = cfg.pinch_click_threshold;
        valPinch.textContent = cfg.pinch_click_threshold;
      }
      if (cfg.scroll_sensitivity) {
        sliderScroll.value = cfg.scroll_sensitivity;
        valScroll.textContent = cfg.scroll_sensitivity;
      }
      if (cfg.active_margin_x) {
        sliderMargin.value = cfg.active_margin_x;
        valMargin.textContent = `${Math.round(cfg.active_margin_x * 100)}%`;
      }
      if (cfg.lock_system_type) selectLockType.value = cfg.lock_system_type;
      if (cfg.lock_hold_duration) {
        sliderLockHold.value = cfg.lock_hold_duration;
        valLockHold.textContent = `${cfg.lock_hold_duration}s`;
      }
      if (cfg.unlock_sequence && cfg.unlock_sequence.length >= 2) {
        selectUnlockStep1.value = cfg.unlock_sequence[0];
        selectUnlockStep2.value = cfg.unlock_sequence[1];
      }
      if (cfg.unlock_pin) inputPin.value = cfg.unlock_pin;
    })
    .catch((err) => console.error("Error loading config:", err));

  // Save Config
  btnSaveSettings.addEventListener("click", () => {
    const payload = {
      camera_id: selectCamera ? parseInt(selectCamera.value) : 1,
      cursor_speed: parseFloat(sliderSpeed.value),
      smoothing: parseFloat(sliderSmoothing.value),
      pinch_click_threshold: parseFloat(sliderPinch.value),
      scroll_sensitivity: parseInt(sliderScroll.value),
      active_margin_x: parseFloat(sliderMargin.value),
      active_margin_y: parseFloat(sliderMargin.value),
      lock_system_type: selectLockType.value,
      lock_hold_duration: parseFloat(sliderLockHold.value),
      unlock_sequence: [selectUnlockStep1.value, selectUnlockStep2.value],
      unlock_pin: inputPin.value
    };

    fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    })
      .then((r) => r.json())
      .then((resp) => {
        if (resp.status === "success") {
          btnSaveSettings.textContent = "Saved ✓";
          setTimeout(() => (btnSaveSettings.textContent = "Save Changes"), 1500);
          playSound("click");
        }
      });
  });

  // Action Buttons
  btnToggleMouse.addEventListener("click", () => {
    fetch("/api/action/toggle_mouse", { method: "POST" })
      .then((r) => r.json())
      .then((data) => {
        toggleMouseText.textContent = data.mouse_enabled
          ? "Disable Virtual Mouse"
          : "Enable Virtual Mouse";
        playSound("click");
      });
  });

  btnLockNow.addEventListener("click", () => {
    fetch("/api/action/lock", { method: "POST" });
    playSound("lock");
  });

  btnUnlockNow.addEventListener("click", () => {
    fetch("/api/action/unlock", { method: "POST" });
    playSound("unlock");
  });

  // Telemetry Poller (10Hz)
  setInterval(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then((data) => {
        // Status indicator
        if (data.is_locked) {
          statusIndicator.classList.add("locked");
          statusText.textContent = "LAPTOP LOCKED";
          lockOverlayBanner.style.display = "flex";
          unlockInstructionText.textContent = `Present: ${data.unlock_target || "Sequence"} to unlock`;
          if (!wasLocked) {
            playSound("lock");
            wasLocked = true;
          }
        } else {
          statusIndicator.classList.remove("locked");
          statusText.textContent = data.mouse_enabled ? "SYSTEM ACTIVE" : "MOUSE PAUSED";
          lockOverlayBanner.style.display = "none";
          if (wasLocked) {
            playSound("unlock");
            wasLocked = false;
          }
        }

        // FPS & Badges
        fpsCounter.textContent = data.fps;
        hudGestureBadge.textContent = `GESTURE: ${data.current_gesture.toUpperCase()}`;
        hudActionBadge.textContent = data.current_action;

        // Telemetry
        telemAction.textContent = data.current_action;
        telemGesture.textContent = data.current_gesture;
        const progPct = Math.round(data.lock_progress * 100);
        telemLockProg.style.width = `${progPct}%`;

        // Passcode PIN buffer representation
        const elPin = document.getElementById("telem-pin");
        if (elPin && data.target_pin_len) {
          const entered = data.entered_pin || "";
          let pinBoxes = [];
          for (let i = 0; i < data.target_pin_len; i++) {
            if (i < entered.length) {
              pinBoxes.push(`[ ${entered[i]} ]`);
            } else {
              pinBoxes.push("[ _ ]");
            }
          }
          elPin.textContent = pinBoxes.join(" ");
        }

        const elDigitSign = document.getElementById("telem-digit-sign");
        if (elDigitSign) {
          elDigitSign.textContent = data.detected_digit_sign ? `Sign [ ${data.detected_digit_sign} ]` : "None";
        }

        const elKeyHover = document.getElementById("telem-key-hover");
        if (elKeyHover) {
          elKeyHover.textContent = data.active_hover_key ? `Key [ ${data.active_hover_key} ]` : "None";
        }

        if (data.is_locked) {
          unlockInstructionText.textContent = "Show Peace Sign (✌️) or Open Palm (🖐️) to Instant Unlock, or use Virtual Keyboard / Signs 1-9";
        }
      })
      .catch(() => {});
  }, 100);
});
