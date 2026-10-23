import fs from "node:fs";
import path from "node:path";

const durationSeconds = Number(process.argv[2] ?? 60);
const output = path.resolve(process.argv[3] ?? "data/raw_events.jsonl");
if (!Number.isFinite(durationSeconds) || durationSeconds < 5) {
  throw new Error("Duration must be at least five seconds");
}

fs.mkdirSync(path.dirname(output), { recursive: true });
const stream = fs.createWriteStream(output, { flags: "a" });
const socket = new WebSocket("wss://api.hyperliquid.xyz/ws");
let messages = 0;
let books = 0;
let bbo = 0;
let trades = 0;
let finished = false;

function finish(code, reason) {
  if (finished) return;
  finished = true;
  clearInterval(heartbeat);
  clearTimeout(deadline);
  if (socket.readyState === WebSocket.OPEN) socket.close(1000, reason);
  stream.end(() => {
    process.stdout.write(JSON.stringify({ output, durationSeconds, messages, books, bbo, trades, reason }) + "\n");
    process.exit(code);
  });
}

socket.addEventListener("open", () => {
  socket.send(JSON.stringify({ method: "subscribe", subscription: { type: "l2Book", coin: "BTC" } }));
  socket.send(JSON.stringify({ method: "subscribe", subscription: { type: "bbo", coin: "BTC" } }));
  socket.send(JSON.stringify({ method: "subscribe", subscription: { type: "trades", coin: "BTC" } }));
});

socket.addEventListener("message", (event) => {
  const receivedAtMs = Date.now();
  let payload;
  try {
    payload = JSON.parse(String(event.data));
  } catch {
    return;
  }
  messages += 1;
  if (payload.channel === "l2Book") books += 1;
  if (payload.channel === "bbo") bbo += 1;
  if (payload.channel === "trades") trades += Array.isArray(payload.data) ? payload.data.length : 1;
  stream.write(JSON.stringify({ receivedAtMs, payload }) + "\n");
});

socket.addEventListener("error", () => finish(1, "websocket error"));
socket.addEventListener("close", (event) => {
  if (!finished) finish(event.wasClean ? 0 : 1, `closed ${event.code}`);
});

const heartbeat = setInterval(() => {
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ method: "ping" }));
  }
}, 30_000);

const deadline = setTimeout(() => finish(0, "collection complete"), durationSeconds * 1_000);
