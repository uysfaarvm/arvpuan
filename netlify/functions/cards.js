/**
 * Netlify Serverless Function — kart sonuçlarını alır ve saklar.
 * Endpoint: POST /.netlify/functions/cards
 */

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  // Secret doğrulama
  const secret = process.env.SECRET_KEY;
  if (secret) {
    const incoming = event.headers["x-secret"] || "";
    if (incoming !== secret) {
      return { statusCode: 401, body: "Unauthorized" };
    }
  }

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch {
    return { statusCode: 400, body: "Invalid JSON" };
  }

  // Özet mesajı
  if (payload.type === "summary") {
    console.log(`[SUMMARY] LIVE:${payload.live} DEAD:${payload.dead} ERR:${payload.error}`);
    return { statusCode: 200, body: JSON.stringify({ ok: true, type: "summary" }) };
  }

  // Sadece LIVE kartları işle
  if (!payload.success || !payload.has_points) {
    return { statusCode: 200, body: JSON.stringify({ ok: true, skipped: true }) };
  }

  const entry = {
    card:     payload.card,
    points:   payload.formatted,
    bank:     payload.bank,
    program:  payload.program,
    expiry:   payload.expiry,
    saved_at: new Date().toISOString(),
  };

  console.log(`[LIVE] ${entry.card} | ${entry.points} | ${entry.bank}`);

  // Netlify Blobs'a kaydet (opsiyonel, hata olursa atla)
  try {
    const { getStore } = require("@netlify/blobs");
    const store = getStore("live-cards");
    const key   = `${Date.now()}-${payload.card || "unknown"}`;
    await store.setJSON(key, entry);
  } catch (err) {
    console.log("Blobs kayit atlandi:", err.message);
  }

  // Başka bir webhook'a ilet (opsiyonel)
  const forwardUrl = process.env.WEBHOOK_FORWARD_URL;
  if (forwardUrl) {
    try {
      await fetch(forwardUrl, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(payload),
      });
    } catch (err) {
      console.error("Forward hatasi:", err.message);
    }
  }

  return {
    statusCode: 200,
    body: JSON.stringify({ ok: true, card: payload.card }),
  };
};
