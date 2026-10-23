import fs from "node:fs";
import path from "node:path";

const durationSeconds = Number(process.argv[2] ?? 60);
const output = path.resolve(process.argv[3] ?? "data/cross_venue_events.jsonl");
if (!Number.isFinite(durationSeconds) || durationSeconds < 5) throw new Error("Duration must be at least five seconds");

fs.mkdirSync(path.dirname(output), { recursive: true });
const stream = fs.createWriteStream(output, { flags: "a" });
const sockets = [];
const counts = { hyperliquid: 0, binance: 0 };
let finished = false;

function write(venue, channel, payload) {
  counts[venue] += 1;
  stream.write(JSON.stringify({ venue, channel, receivedAtMs: Date.now(), payload }) + "\n");
}

const hyperliquid = new WebSocket("wss://api.hyperliquid.xyz/ws");
sockets.push(hyperliquid);
hyperliquid.addEventListener("open", () => {
  hyperliquid.send(JSON.stringify({ method: "subscribe", subscription: { type: "l2Book", coin: "BTC" } }));
  hyperliquid.send(JSON.stringify({ method: "subscribe", subscription: { type: "bbo", coin: "BTC" } }));
  hyperliquid.send(JSON.stringify({ method: "subscribe", subscription: { type: "trades", coin: "BTC" } }));
});
hyperliquid.addEventListener("message", event => {
  try {
    const payload = JSON.parse(String(event.data));
    if (["l2Book", "bbo", "trades"].includes(payload.channel)) write("hyperliquid", payload.channel, payload);
  } catch {}
});

const binance = new WebSocket("wss://stream.binance.com:9443/ws/btcusdt@bookTicker");
sockets.push(binance);
binance.addEventListener("message", event => {
  try { write("binance", "bookTicker", JSON.parse(String(event.data))); } catch {}
});

function finish(reason) {
  if (finished) return;
  finished = true;
  clearInterval(heartbeat);
  clearTimeout(deadline);
  for (const socket of sockets) if (socket.readyState === WebSocket.OPEN) socket.close(1000, reason);
  stream.end(() => {
    process.stdout.write(JSON.stringify({ output, durationSeconds, counts, reason }) + "\n");
    process.exit(0);
  });
}

for (const socket of sockets) socket.addEventListener("error", () => finish("websocket error"));
const heartbeat = setInterval(() => {
  if (hyperliquid.readyState === WebSocket.OPEN) hyperliquid.send(JSON.stringify({ method: "ping" }));
}, 30_000);
const deadline = setTimeout(() => finish("collection complete"), durationSeconds * 1_000);
