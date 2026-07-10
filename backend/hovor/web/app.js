/* HOVOR! web client — the same REST contract the iOS client consumes.
   Text input everywhere; push-to-talk via the browser's Slovak speech
   recognition where available (input_mode=speech so the backend treats it
   as a transcript). */

// Served at {prefix}/app/ — locally the prefix is empty; behind the
// boundstate.ai reverse proxy it is /hovor. Derive it, don't hardcode it.
const ROOT = location.pathname.replace(/\/app(\/.*)?$/, "");
const API = ROOT + "/api/v1";
let user = null;
let session = null;   // {session_id, plan}
let voice = null;     // {voice_session_id, mission_id}
let promptShownAt = null;

const $ = (sel) => document.querySelector(sel);
const screen = () => $("#screen");

async function api(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

/* ---------- sidebar ---------- */

async function refreshSidebar() {
  if (!user) return;
  const [profile, map, streak, ach, health] = await Promise.all([
    api("GET", `/users/${user.id}/profile`),
    api("GET", `/users/${user.id}/map`),
    api("GET", `/users/${user.id}/streak`),
    api("GET", `/users/${user.id}/achievements`),
    fetch(ROOT + "/health").then((r) => r.json()),
  ]);
  $("#user-box").innerHTML = `<b>${user.name}</b>
    <label class="small" title="Missions speak with the live AI tutor (needs server key; costs per turn)">
    <input type="checkbox" id="live-tutor" ${liveTutor() ? "checked" : ""}> live tutor 🎙</label>`;
  $("#live-tutor").onchange = (e) =>
    localStorage.setItem("hovor_live_tutor", e.target.checked ? "1" : "0");
  $("#stats").innerHTML =
    `XP <b>${profile.total_xp}</b> · streak <b>${streak.days}</b>d` +
    (streak.shields ? ` · 🛡×${streak.shields}` : "");
  $("#map").innerHTML = map.regions
    .map((r) => {
      const missions = r.missions
        .map((m) => `<div class="${m.completed ? "done" : ""}">${m.completed ? "✓" : "•"} ${m.title}</div>`)
        .join("") || `<div>(${r.status})</div>`;
      return `<div class="region ${r.unlocked ? "" : "locked"}">
        <b>${r.unlocked ? "" : "🔒 "}${r.title}</b><div class="missions">${missions}</div></div>`;
    })
    .join("");
  $("#achievements").innerHTML =
    ach.achievements.map((a) => `<span class="badge" title="${a.description}">${a.title}</span>`).join("") ||
    `<span class="small">none yet</span>`;
  $("#review-flag").textContent =
    `content ${health.content_version} · ${health.content_review_status.replace(/_/g, " ").toLowerCase()}`;
}

/* ---------- login ---------- */

function showLogin() {
  screen().innerHTML = `<div class="card">
    <div class="phase-label">Začíname</div>
    <div class="prompt">Who's learning?</div>
    <div class="row"><input type="text" id="name" placeholder="Your name">
    <button id="go">Start</button></div></div>`;
  $("#go").onclick = async () => {
    const name = $("#name").value.trim() || "Učeník";
    user = await api("POST", "/users", { name });
    localStorage.setItem("hovor_user", JSON.stringify(user));
    await refreshSidebar();
    showHome();
  };
}

function showHome() {
  screen().innerHTML = `<div class="card">
    <div class="phase-label">Daily loop</div>
    <div class="prompt">Ready?</div>
    <p class="instruction">Retrieval ambush → new material → voice mission → debrief. 10–15 minutes.</p>
    <button id="start">Začať hovoriť 🎙</button></div>`;
  $("#start").onclick = startSession;
}

/* ---------- session flow ---------- */

async function startSession() {
  session = await api("POST", "/learning-sessions", { user_id: user.id });
  session.queue = [];
  for (const ex of session.plan.phase_a) session.queue.push({ kind: "exercise", phase: "A — retrieval ambush", ex });
  for (const item of session.plan.phase_b) {
    session.queue.push({ kind: "introduce", phase: "B — new material", item: item.introduce });
    session.queue.push({ kind: "exercise", phase: "B — say it back", ex: item.exercise });
  }
  for (const ex of session.plan.phase_b_recall || []) {
    session.queue.push({ kind: "exercise", phase: "B — pamätáš si? (recall)", ex });
  }
  session.queue.push({ kind: "mission", phase: "C — voice mission" });
  nextStep();
}

function nextStep() {
  const step = session.queue.shift();
  if (!step) return showDebrief();
  if (step.kind === "introduce") return showIntroduce(step);
  if (step.kind === "exercise") return showExercise(step);
  if (step.kind === "mission") return startMission();
}

function showIntroduce(step) {
  const it = step.item;
  screen().innerHTML = `<div class="card">
    <div class="phase-label">Phase ${step.phase}</div>
    <div class="prompt">${it.slovak} ${speakBtn("spk-intro")}</div>
    <div class="instruction">${it.english} <span class="small">(${it.register})</span></div>
    <button id="next">Got it</button></div>`;
  const say = wireSpeak("spk-intro", it.slovak);
  if (say) say(); // model the sound the moment a word is introduced
  $("#next").onclick = nextStep;
}

function showExercise(step) {
  const ex = step.ex;
  promptShownAt = Date.now();
  // listen_type is a true listening exercise: hide the text, play the audio.
  // If TTS can't run, reveal the text — a broken speaker never blocks learning.
  const isListening = ex.type === "listen_type";
  const promptHtml = isListening
    ? `<span id="ptext" style="display:none">${ex.prompt}</span><span id="pmask">🎧 …</span> ${speakBtn("spk-ex")}`
    : `${ex.prompt} ${speakBtn("spk-ex")}${ex.contrast_with ? ` <span class="small">vs ${ex.contrast_with}</span>` : ""}`;
  screen().innerHTML = `<div class="card">
    <div class="phase-label">Phase ${step.phase} · ${ex.type}</div>
    <div class="prompt">${promptHtml}</div>
    <div class="instruction">${ex.instruction}${ex.time_budget_ms ? " ⏱" : ""}</div>
    <div class="row"><input type="text" id="answer" autocomplete="off">
    ${micButton()}<button id="submit">Answer</button></div>
    <div id="fb"></div></div>`;
  const say = wireSpeak("spk-ex", ex.prompt, isListening ? () => {
    $("#ptext").style.display = "";
    $("#pmask").style.display = "none";
  } : null);
  if (isListening && say) say();
  const submit = async () => {
    const response = $("#answer").value.trim();
    if (!response) return;
    const out = await api("POST", "/attempts", {
      user_id: user.id, session_id: session.session_id,
      exercise_id: ex.exercise_id, response,
      latency_ms: Date.now() - promptShownAt,
      input_mode: window._lastInputWasSpeech ? "speech" : "text",
    });
    window._lastInputWasSpeech = false;
    if (isListening) {
      // Answer's in: reveal what was actually said.
      $("#ptext").style.display = "";
      $("#pmask").style.display = "none";
    }
    let cls = out.semantic_success ? "ok" : "bad";
    let msg = out.semantic_success ? "✓ Correct" : "✗ Not quite";
    // A miss shows the corrected form (spec §12) — never a raw error tag.
    if (!out.semantic_success && out.expected) {
      msg += ` — it's: <b>${out.expected}</b>${out.expected_speakable ? " " + speakBtn("spk-fix") : ""}`;
    }
    if (out.xp_awarded) msg += ` <span class="xp-pop">+${out.xp_awarded} XP</span>`;
    if (out.note) { cls = "note"; msg = out.note; }
    $("#fb").innerHTML = `<div class="feedback ${cls}">${msg}</div>` +
      (out.focus.state !== "ok" ? `<div class="feedback note">${out.focus.advice}</div>` : "") +
      (out.achievements || []).map((a) => `<div class="feedback note">🏅 ${a.title}</div>`).join("") +
      `<div class="row"><button id="next">Continue</button></div>`;
    if (out.expected_speakable) {
      const sayFix = wireSpeak("spk-fix", out.expected);
      if (sayFix) sayFix(); // hear the correct form the moment you miss it
    }
    $("#next").onclick = () => { refreshSidebar(); nextStep(); };
  };
  $("#submit").onclick = submit;
  $("#answer").onkeydown = (e) => e.key === "Enter" && submit();
  wireMic($("#answer"), submit); // release-to-send
  $("#answer").focus();
}

/* ---------- mission ---------- */

function liveTutor() {
  return localStorage.getItem("hovor_live_tutor") === "1";
}

/* Pronunciation on demand: GET /tts only speaks known content strings, so a
   rejected play (English prompt, no key) just greys the button out. */
function speakBtn(id) {
  return `<button class="spk" id="${id}" title="Hear it">🔊</button>`;
}

function wireSpeak(id, text, onFail) {
  const btn = $(`#${id}`);
  if (!btn) return;
  let current = null; // single-flight: first play synthesizes (~2s), and an
                      // impatient second tap must not stack an echo on it
  const say = () => {
    if (current) { current.pause(); current = null; }
    const audio = new Audio(`${API}/tts?text=${encodeURIComponent(text)}`);
    current = audio;
    btn.classList.add("loading");
    audio.onplaying = () => btn.classList.remove("loading");
    audio.onended = () => { if (current === audio) current = null; };
    audio.play().catch(() => {
      btn.classList.remove("loading");
      btn.style.opacity = 0.25;
      btn.disabled = true;
      if (onFail) onFail();
    });
  };
  btn.onclick = say;
  return say;
}

function playTutorAudio(b64) {
  if (!b64) return;
  new Audio("data:audio/wav;base64," + b64).play().catch(() => {});
}

async function startMission() {
  const mission = session.plan.phase_c;
  voice = await api("POST", "/voice-sessions", {
    user_id: user.id, mission_id: mission.mission_id, learning_session_id: session.session_id,
    provider_config: liveTutor() ? { provider: "openai-realtime" } : {},
  });
  screen().innerHTML = `<div class="card">
    <div class="phase-label">Phase C — ${mission.region}</div>
    <div class="prompt">${mission.title}</div>
    <p class="instruction">${mission.briefing}</p>
    <div class="objectives" id="obj"></div>
    <div class="chat" id="chat"></div>
    <div class="row"><input type="text" id="say" placeholder="Povedz niečo po slovensky..." autocomplete="off">
    ${micButton()}<button id="send">Povedz to</button></div></div>`;
  addMsg("tutor", voice.tutor_text, voice.tutor_english);
  if (voice.provider_degraded) {
    addMsg("hint", "⚠ live tutor unavailable right now — running the scripted tutor instead.");
  }
  updateObjectives(voice.objective_state);
  const send = async () => {
    const text = $("#say").value.trim();
    if (!text) return;
    $("#say").value = "";
    addMsg("learner", text);
    const r = await api("POST", `/voice-sessions/${voice.voice_session_id}/turns`, { text });
    if (r.provider_failure) {
      addMsg("hint", "⚠ voice connection lost — continuing in push-to-talk. Nothing was scored against you.");
      return;
    }
    if (r.hint) addMsg("hint", `💡 ${r.hint.text}`);
    addMsg("tutor", r.tutor_text, r.tutor_english);
    playTutorAudio(r.tutor_audio_b64);
    updateObjectives(r.objective_state);
    (r.achievements || []).forEach((a) => addMsg("hint", `🏅 ${a.title} — ${a.description}`));
    if (r.mission_complete) {
      addMsg("hint", "🎉 Mission complete!");
      setTimeout(() => { refreshSidebar(); showDebrief(); }, 1600);
    }
  };
  $("#send").onclick = send;
  $("#say").onkeydown = (e) => e.key === "Enter" && send();
  wireMic($("#say"), send); // release-to-send
  $("#say").focus();
}

function addMsg(role, text, gloss) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = text + (gloss ? `<span class="gloss">${gloss}</span>` : "");
  $("#chat").appendChild(div);
  $("#chat").scrollTop = 1e6;
}

function updateObjectives(state) {
  const total = Object.keys(state).length;
  const done = Object.values(state).filter((o) => o.status === "completed").length;
  $("#obj").textContent = `hidden objectives: ${done}/${total}`;
}

/* ---------- debrief ---------- */

async function showDebrief() {
  const d = await api("GET", `/learning-sessions/${session.session_id}/debrief`);
  const errs = d.important_errors
    .map((e) => `<li>${e.error_tag}${e.recurring ? " <b>(recurring)</b>" : ""}</li>`).join("");
  screen().innerHTML = `<div class="card debrief">
    <div class="phase-label">Phase D — debrief</div>
    <div class="prompt">Session done. <span class="xp-pop">+${d.xp} XP</span></div>
    <h3>What worked</h3>
    <p>${d.what_worked.successful_attempts} successful attempts${
      d.what_worked.items.length ? ": " + d.what_worked.items.join(", ") : ""}</p>
    ${errs ? `<h3>Worth fixing</h3><ul>${errs}</ul>` : ""}
    ${d.failed_retrievals.length ? `<h3>Couldn't retrieve</h3><p>${d.failed_retrievals.join(", ")} — coming back soon.</p>` : ""}
    <p class="small">${d.next_review_implication}</p>
    <div class="row"><button id="again">Ešte raz — another session</button></div></div>`;
  $("#again").onclick = startSession;
  refreshSidebar();
}

/* ---------- speech input (browser Slovak ASR where available) ---------- */

function micButton() {
  const supported = !!(navigator.mediaDevices && window.MediaRecorder);
  return supported ? `<button class="mic" id="mic" title="Podrž a hovor — hold to talk, release to send">🎤</button>` : "";
}

/* Push-to-talk, walkie-talkie style: hold the mic, speak, release — the
   transcript submits itself (onTranscript). One gesture instead of
   tap-stop-tap-answer. Errors are shown on the button — never a silent
   no-op. Typing always remains available. */
function wireMic(input, onTranscript) {
  const btn = $("#mic");
  if (!btn) return;
  let recorder = null;
  let autoStop = null;
  let held = false;
  let startedAt = 0;

  const fail = (label) => {
    btn.classList.remove("listening", "busy");
    btn.textContent = label;
    setTimeout(() => (btn.textContent = "🎤"), 2500);
  };

  // Mic denial must explain itself — "blocked" with no way forward is a dead
  // end, and on iOS the fix lives in Settings, not on this page.
  const micHelp = (err) => {
    fail("🎤 blocked");
    if ($("#michelp")) return;
    const inApp = /FBAN|FBAV|Instagram|Twitter|GSA|Line|Snapchat/i.test(navigator.userAgent);
    let how;
    if (inApp) {
      how = "You're in another app's built-in browser, which never allows the mic. Open this page in Safari or Chrome directly.";
    } else if (err && err.name === "NotFoundError") {
      how = "No microphone was found on this device.";
    } else if (/iPhone|iPad/.test(navigator.userAgent)) {
      how = "Allow the mic for this site: tap <b>ᴀA</b> in the address bar → Website Settings → Microphone → Allow. " +
            "If there's no Microphone entry, check Settings → Apps → Safari → Microphone. " +
            "If you opened this link from another app, open it in Safari itself.";
    } else {
      how = "Allow microphone access for this site in your browser's site settings (usually the icon left of the address bar), then try again.";
    }
    btn.closest(".card").insertAdjacentHTML(
      "beforeend",
      `<div class="feedback note" id="michelp">🎤 ${how} <i>(You can always type instead.)</i></div>`
    );
  };

  const start = async () => {
    if (recorder) return;
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      return micHelp(err);
    }
    const chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.onstop = async () => {
      clearTimeout(autoStop);
      stream.getTracks().forEach((t) => t.stop());
      btn.classList.remove("listening");
      const heldMs = Date.now() - startedAt;
      const mime = (recorder && recorder.mimeType) || "audio/webm";
      recorder = null;
      if (heldMs < 350) {
        // An accidental tap, not speech — teach the gesture.
        return fail("podrž 🎤");
      }
      btn.classList.add("busy");
      btn.textContent = "…";
      try {
        const blob = new Blob(chunks, { type: mime });
        const fd = new FormData();
        fd.append("audio", blob, "speech." + (mime.includes("mp4") ? "mp4" : "webm"));
        const res = await fetch(`${API}/transcribe`, { method: "POST", body: fd });
        if (!res.ok) throw new Error(res.status);
        const out = await res.json();
        btn.classList.remove("busy");
        btn.textContent = "🎤";
        if (!out.text) return fail("🎤 nič?");
        input.value = out.text;
        window._lastInputWasSpeech = true;
        // Release = said it. Submit like a spoken turn, no extra tap.
        if (onTranscript) onTranscript();
        else input.focus();
      } catch {
        fail("🎤 offline");
      }
    };
    recorder.start();
    startedAt = Date.now();
    btn.classList.add("listening");
    btn.textContent = "🔴";
    autoStop = setTimeout(() => recorder && recorder.state === "recording" && recorder.stop(), 15000);
    if (!held) recorder.stop(); // released before the mic warmed up
  };

  const stop = () => {
    held = false;
    if (recorder && recorder.state === "recording") recorder.stop();
  };

  btn.onpointerdown = (e) => {
    e.preventDefault();
    if (btn.classList.contains("busy")) return;
    try { btn.setPointerCapture(e.pointerId); } catch {}
    held = true;
    start();
  };
  btn.onpointerup = btn.onpointercancel = stop;
  btn.oncontextmenu = (e) => e.preventDefault(); // iOS long-press menu
}

/* ---------- boot ---------- */

(async function boot() {
  const saved = localStorage.getItem("hovor_user");
  if (saved) {
    user = JSON.parse(saved);
    try {
      await api("GET", `/users/${user.id}/profile`);
    } catch { user = null; localStorage.removeItem("hovor_user"); }
  }
  if (user) { await refreshSidebar(); showHome(); } else showLogin();
})();
