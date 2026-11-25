"use strict";
const $ = (id) => document.getElementById(id);
const labels = {
  discovery: "需求探索",
  objection: "价格异议",
  product: "产品知识",
  relationship: "客户关系",
  practice: "实战演练",
  clarify: "澄清目标",
  pending: "等待执行",
  routing: "意图路由",
  recommending: "专家推荐",
  retrieving: "知识检索",
  generating: "生成中",
  retrying: "重试",
  completed: "已完成",
  degraded: "已降级",
  failed: "执行失败",
};
let sid = localStorage.getItem("jewelmentor-session");
let experts = [];
let busy = false;
let pending = null;
let failedPayload = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json" },
  });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(
      data.error?.message || `请求失败 (${response.status})`,
    );
    error.status = response.status;
    throw error;
  }
  return data;
}
function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}
function setBusy(value) {
  busy = value;
  for (const el of [
    $("send"),
    $("reset"),
    $("expert"),
    $("resume"),
    ...document.querySelectorAll("[data-prompt]"),
  ])
    el.disabled = value;
  $("input").disabled = value;
  $("send").textContent = value ? "教练思考中…" : "开始训练 ↑";
}
function addMessage(role, content) {
  $("messages").querySelector(".welcome")?.remove();
  const wrapper = document.createElement("article");
  wrapper.className = `message ${role}`;
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "YOU / 你的提问" : "COACH / 教练反馈";
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = content;
  wrapper.append(label, body);
  $("messages").append(wrapper);
  $("messages").scrollTop = $("messages").scrollHeight;
}
function renderResult(result) {
  $("turn-state").textContent = labels[result.state] || result.state;
  $("intent").textContent = labels[result.route.intent];
  $("active-expert").textContent =
    experts.find((e) => e.id === result.expert_id)?.name || result.expert_id;
  $("route-reason").textContent = result.route.reason;
  $("trace-id").textContent = `TRACE ${result.trace_id}`;
  $("evidence").replaceChildren();
  for (const item of result.evidence) {
    const details = document.createElement("details"),
      summary = document.createElement("summary"),
      body = document.createElement("p"),
      source = document.createElement("p");
    summary.textContent = `[${item.id}] ${item.title}`;
    body.textContent = item.content;
    source.textContent = item.source;
    details.append(summary, body, source);
    $("evidence").append(details);
  }
  if (!result.evidence.length)
    $("evidence").textContent = "暂无匹配依据；请补充场景。";
}
async function refresh() {
  const session = await api(`/api/sessions/${sid}`);
  $("messages").replaceChildren();
  for (const msg of session.messages) addMessage(msg.role, msg.content);
  const turns = session.turns;
  pending =
    turns.find((t) => !["completed", "degraded", "failed"].includes(t.state)) ||
    null;
  $("recovery").hidden = !pending;
  const events = await api(`/api/sessions/${sid}/traces`);
  const last = turns.at(-1);
  $("trace").replaceChildren();
  for (const event of events.filter((e) => e.turn_id === last?.id)) {
    const li = document.createElement("li"),
      detail = document.createElement("small");
    li.textContent = `${labels[event.state] || event.state} · ${event.node}`;
    detail.textContent = `${new Date(event.timestamp * 1000).toLocaleTimeString()}${event.attempt ? ` · 尝试 ${event.attempt}` : ""}${event.error_category ? ` · ${event.error_category}` : ""}`;
    li.append(detail);
    $("trace").append(li);
  }
  // Terminal resume is a read-only idempotent replay of the stored result.
  if (last && !pending)
    renderResult(
      await api(`/api/sessions/${sid}/turns/${last.id}/resume`, {
        method: "POST",
      }),
    );
  if (!last) {
    $("turn-state").textContent = "等待输入";
    $("intent").textContent = "—";
    $("active-expert").textContent = "自动推荐";
    $("route-reason").textContent = "发送消息后展示路由依据。";
    $("trace-id").textContent = "";
    $("evidence").textContent = "回答关联的知识记录会展示在这里。";
  }
}
async function newSession() {
  const session = await api("/api/sessions", { method: "POST" });
  sid = session.id;
  localStorage.setItem("jewelmentor-session", sid);
  failedPayload = null;
}
async function send(event) {
  event.preventDefault();
  if (busy || !$("input").value.trim()) return;
  if (pending) {
    status("请先恢复中断回合，或清除并新建会话。", true);
    return;
  }
  const payload = {
    message: $("input").value.trim(),
    expert_id: $("expert").value || null,
    request_id: crypto.randomUUID(),
  };
  if (
    failedPayload &&
    failedPayload.message === payload.message &&
    failedPayload.expert_id === payload.expert_id
  )
    payload.request_id = failedPayload.request_id;
  setBusy(true);
  status("正在完成意图分析、专家推荐和生成…");
  try {
    const result = await api(`/api/sessions/${sid}/messages`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    failedPayload = null;
    $("input").value = "";
    await refresh();
    renderResult(result);
    status(
      result.error_category
        ? `本轮 ${result.state} · ${result.error_category}`
        : "本轮已保存，可继续追问或切换教练。",
      !!result.error_category,
    );
  } catch (error) {
    failedPayload = payload;
    status(error.message, true);
    try {
      await refresh();
    } catch {
      /* Keep the same request key for a safe retry. */
    }
  } finally {
    setBusy(false);
    $("input").focus();
  }
}
$("chat-form").addEventListener("submit", send);
$("input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("chat-form").requestSubmit();
  }
});
$("scenarios").addEventListener("click", (event) => {
  const button = event.target.closest("[data-prompt]");
  if (button && !busy) {
    $("input").value = button.dataset.prompt;
    $("input").focus();
  }
});
$("expert").addEventListener("change", () => {
  const expert = experts.find((e) => e.id === $("expert").value);
  $("expert-note").textContent = expert
    ? `${expert.name} · ${expert.title}。${expert.principles[0]}。原创虚构角色。`
    : "系统根据本轮场景推荐适合的教练。所有角色均为原创虚构教学人物。";
});
$("reset").addEventListener("click", async () => {
  if (busy || !window.confirm("清除当前会话、记忆和轨迹，并新建训练？")) return;
  setBusy(true);
  try {
    await api(`/api/sessions/${sid}`, { method: "DELETE" });
    await newSession();
    await refresh();
    status("新会话已就绪。");
  } catch (error) {
    status(error.message, true);
  } finally {
    setBusy(false);
  }
});
$("resume").addEventListener("click", async () => {
  if (!pending || busy) return;
  setBusy(true);
  status("正在从检查点恢复…");
  try {
    const result = await api(
      `/api/sessions/${sid}/turns/${pending.id}/resume`,
      { method: "POST" },
    );
    await refresh();
    renderResult(result);
    status(`恢复结束：${labels[result.state]}`, result.state !== "completed");
  } catch (error) {
    status(error.message, true);
  } finally {
    setBusy(false);
  }
});
async function boot() {
  setBusy(true);
  try {
    const health = await api("/health");
    $("mode").textContent =
      health.provider === "demo"
        ? "OFFLINE DEMO · 离线演示"
        : "LIVE MODEL · 实时模型";
    experts = await api("/api/experts");
    for (const expert of experts) {
      const option = document.createElement("option");
      option.value = expert.id;
      option.textContent = `${expert.name} · ${expert.title}`;
      $("expert").append(option);
    }
    if (sid) {
      try {
        await refresh();
      } catch (error) {
        if (error.status === 404) {
          await newSession();
        } else throw error;
      }
    } else await newSession();
    status("准备就绪。离线模式使用示例模板；实时模式调用配置的模型。");
  } catch (error) {
    status(`连接失败：${error.message}`, true);
  } finally {
    setBusy(false);
  }
}
boot();
