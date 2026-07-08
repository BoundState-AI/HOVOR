/* HOVOR! web client — the same REST contract the iOS client consumes.
   Text input everywhere; push-to-talk via the browser's Slovak speech
   recognition where available (input_mode=speech so the backend treats it
   as a transcript). */

const API = "/api/v1";
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
    fetch("/health").then((r) => r.json()),
  ]);
  $("#user-box").innerHTML = `<b>${user.name}</b>`;
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
    <button id="start">Start session</button></div>`;
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
    <div class="prompt">${it.slovak}</div>
    <div class="instruction">${it.english} <span class="small">(${it.register})</span></div>
    <button id="next">Got it</button></div>`;
  $("#next").onclick = nextStep;
}

function showExercise(step) {
  const ex = step.ex;
  promptShownAt = Date.now();
  screen().innerHTML = `<div class="card">
    <div class="phase-label">Phase ${step.phase} · ${ex.type}</div>
    <div class="prompt">${ex.prompt}${ex.contrast_with ? ` <span class="small">vs ${ex.contrast_with}</span>` : ""}</div>
    <div class="instruction">${ex.instruction}${ex.time_budget_ms ? " ⏱" : ""}</div>
    <div class="row"><input type="text" id="answer" autocomplete="off">
    ${micButton()}<button id="submit">Answer</button></div>
    <div id="fb"></div></div>`;
  wireMic($("#answer"));
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
    let cls = out.semantic_success ? "ok" : "bad";
    let msg = out.semantic_success ? "✓ Correct" : "✗ Not quite";
    if (out.error_tags.length) msg += ` — ${out.error_tags.join(", ")}`;
    if (out.xp_awarded) msg += ` <span class="xp-pop">+${out.xp_awarded} XP</span>`;
    if (out.note) { cls = "note"; msg = out.note; }
    $("#fb").innerHTML = `<div class="feedback ${cls}">${msg}</div>` +
      (out.focus.state !== "ok" ? `<div class="feedback note">${out.focus.advice}</div>` : "") +
      (out.achievements || []).map((a) => `<div class="feedback note">🏅 ${a.title}</div>`).join("") +
      `<div class="row"><button id="next">Continue</button></div>`;
    $("#next").onclick = () => { refreshSidebar(); nextStep(); };
  };
  $("#submit").onclick = submit;
  $("#answer").onkeydown = (e) => e.key === "Enter" && submit();
  $("#answer").focus();
}

/* ---------- mission ---------- */

async function startMission() {
  const mission = session.plan.phase_c;
  voice = await api("POST", "/voice-sessions", {
    user_id: user.id, mission_id: mission.mission_id, learning_session_id: session.session_id,
  });
  screen().innerHTML = `<div class="card">
    <div class="phase-label">Phase C — ${mission.region}</div>
    <div class="prompt">${mission.title}</div>
    <p class="instruction">${mission.briefing}</p>
    <div class="objectives" id="obj"></div>
    <div class="chat" id="chat"></div>
    <div class="row"><input type="text" id="say" placeholder="Povedz niečo po slovensky..." autocomplete="off">
    ${micButton()}<button id="send">Say it</button></div></div>`;
  addMsg("tutor", voice.tutor_text, voice.tutor_english);
  updateObjectives(voice.objective_state);
  wireMic($("#say"));
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
    updateObjectives(r.objective_state);
    (r.achievements || []).forEach((a) => addMsg("hint", `🏅 ${a.title} — ${a.description}`));
    if (r.mission_complete) {
      addMsg("hint", "🎉 Mission complete!");
      setTimeout(() => { refreshSidebar(); showDebrief(); }, 1600);
    }
  };
  $("#send").onclick = send;
  $("#say").onkeydown = (e) => e.key === "Enter" && send();
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
    <div class="row"><button id="again">Another session</button></div></div>`;
  $("#again").onclick = startSession;
  refreshSidebar();
}

/* ---------- speech input (browser Slovak ASR where available) ---------- */

function micButton() {
  const supported = "webkitSpeechRecognition" in window || "SpeechRecognition" in window;
  return supported ? `<button class="mic" id="mic" title="Hold to speak Slovak">🎤</button>` : "";
}

function wireMic(input) {
  const btn = $("#mic");
  if (!btn) return;
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new Rec();
  rec.lang = "sk-SK";
  rec.interimResults = false;
  btn.onclick = () => { btn.classList.add("listening"); rec.start(); };
  rec.onresult = (e) => {
    input.value = e.results[0][0].transcript;
    window._lastInputWasSpeech = true;
    btn.classList.remove("listening");
  };
  rec.onerror = rec.onend = () => btn.classList.remove("listening");
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
