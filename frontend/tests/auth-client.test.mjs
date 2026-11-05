import assert from "node:assert/strict";
import { after, afterEach, test } from "node:test";

const originalFetch = globalThis.fetch;
let mockFetch = async () => { throw new Error("Unexpected network call"); };
globalThis.fetch = (...args) => mockFetch(...args);
const { api, setTokenProviders, AppCheckUnavailableError } = await import("../src/lib/api/client.ts");
after(() => { globalThis.fetch = originalFetch; });
afterEach(() => {
  mockFetch = async () => { throw new Error("Unexpected network call"); };
  setTokenProviders({ idToken: null, appCheck: null, identity: null });
});
const problem = (code, status = 401) => Response.json({ code, status }, { status });

test("guest requests omit Auth; protected search still carries App Check", async () => {
  setTokenProviders({ idToken: async () => null, appCheck: async () => "app-token" });
  mockFetch = async (request) => {
    assert.equal(request.headers.get("Authorization"), null);
    assert.equal(request.headers.get("X-Firebase-AppCheck"), "app-token");
    return Response.json({ ok: true });
  };
  await api.POST("/v1/endpoints/places/search", { body: { q: "museum" } });
});

test("feedback requires App Check without an ID token", async () => {
  setTokenProviders({ idToken: async () => null, appCheck: async () => "app-token" });
  mockFetch = async (request) => {
    assert.equal(request.headers.get("X-Firebase-AppCheck"), "app-token");
    return Response.json({ status: "received" }, { status: 201 });
  };
  await api.POST("/v1/feedback", { body: { type: "other", content: "hi" } });
});

test("expired token forces one refresh and preserves POST body and operation key", async () => {
  const refreshes = [];
  const bodies = [];
  let calls = 0;
  setTokenProviders({ identity: () => "user-a", idToken: async (force) => {
    refreshes.push(Boolean(force));
    return force ? "new-token" : "old-token";
  }, appCheck: async () => "app-token" });
  mockFetch = async (request) => {
    calls++;
    bodies.push(await request.text());
    assert.equal(request.headers.get("Idempotency-Key"), "same-operation");
    assert.equal(request.headers.get("X-Firebase-AppCheck"), "app-token");
    assert.equal(request.headers.get("Authorization"), `Bearer ${calls === 1 ? "old-token" : "new-token"}`);
    return calls === 1 ? problem("AUTH_TOKEN_EXPIRED") : Response.json({ ok: true });
  };
  const { response } = await api.POST("/v1/trips/check", {
    headers: { "Idempotency-Key": "same-operation" },
    body: { query_id: "same-query", expected_revision: 7, stops: [], conditions: {} },
  });
  assert.equal(response.status, 200);
  assert.equal(calls, 2);
  assert.deepEqual(refreshes, [false, true]);
  assert.equal(bodies[0], bodies[1]);
  assert.equal(JSON.parse(bodies[1]).expected_revision, 7);
});

test("a second expired response is returned without a retry loop", async () => {
  let calls = 0;
  setTokenProviders({ identity: () => "user-a", idToken: async () => "token" });
  mockFetch = async () => { calls++; return problem("AUTH_TOKEN_EXPIRED"); };
  const { error } = await api.GET("/v1/me");
  assert.equal(error.code, "AUTH_TOKEN_EXPIRED");
  assert.equal(calls, 2);
});

for (const [code, status] of [["AUTH_REAUTH_REQUIRED", 401], ["APP_CHECK_FAILED", 403], ["ACCOUNT_DELETING", 403]]) {
  test(`${code} never refreshes or retries`, async () => {
    let calls = 0;
    let forced = 0;
    setTokenProviders({ identity: () => "user-a", idToken: async (force) => { if (force) forced++; return "token"; } });
    mockFetch = async () => { calls++; return problem(code, status); };
    await api.GET("/v1/me");
    assert.equal(calls, 1);
    assert.equal(forced, 0);
  });
}

test("switching accounts during refresh never resends the old account's request", async () => {
  let identity = "user-a";
  let calls = 0;
  setTokenProviders({ identity: () => identity, idToken: async (force) => {
    if (force) identity = "user-b";
    return "token";
  } });
  mockFetch = async () => { calls++; return problem("AUTH_TOKEN_EXPIRED"); };
  const { response } = await api.GET("/v1/me");
  assert.equal(response.status, 401);
  assert.equal(calls, 1);
});

test("an identity change while obtaining App Check stops the original request", async () => {
  let identity = "user-a";
  let calls = 0;
  setTokenProviders({ identity: () => identity, idToken: async () => "token-a", appCheck: async () => {
    identity = "user-b";
    return "app-token";
  } });
  mockFetch = async () => { calls++; return Response.json({}); };
  await assert.rejects(api.POST("/v1/endpoints/places/search", { body: { q: "museum" } }), /AUTH_SESSION_CHANGED/);
  assert.equal(calls, 0);
});

test("refresh failure preserves the original structured error", async () => {
  let calls = 0;
  setTokenProviders({ identity: () => "user-a", idToken: async (force) => {
    if (force) throw new Error("refresh failed");
    return "token";
  } });
  mockFetch = async () => { calls++; return problem("AUTH_TOKEN_INVALID"); };
  const { error } = await api.GET("/v1/me");
  assert.equal(error.code, "AUTH_TOKEN_INVALID");
  assert.equal(calls, 1);
});

test("writes without a defined idempotency mechanism are not replayed", async () => {
  let calls = 0;
  setTokenProviders({ identity: () => "user-a", idToken: async () => "token" });
  mockFetch = async () => { calls++; return problem("AUTH_TOKEN_EXPIRED"); };
  await api.POST("/v1/favorites", { body: {} });
  assert.equal(calls, 1);
});

test("cancel registration is replayed once after an expired token", async () => {
  let calls = 0;
  setTokenProviders({ identity: () => "user-a", idToken: async (force) => (force ? "new-token" : "old-token") });
  mockFetch = async (request) => {
    calls++;
    assert.equal(request.method, "DELETE");
    return calls === 1 ? problem("AUTH_TOKEN_EXPIRED") : new Response(null, { status: 204 });
  };
  const { response } = await api.DELETE("/v1/me/registration");
  assert.equal(response.status, 204);
  assert.equal(calls, 2);
});

test("an aborted request is not replayed after refresh", async () => {
  let calls = 0;
  const controller = new AbortController();
  setTokenProviders({ identity: () => "user-a", idToken: async (force) => {
    if (force) controller.abort();
    return "token";
  } });
  mockFetch = async () => { calls++; return problem("AUTH_TOKEN_EXPIRED"); };
  await api.GET("/v1/me", { signal: controller.signal });
  assert.equal(calls, 1);
});

test("an App Check failure stops protected requests before sending", async () => {
  let calls = 0;
  mockFetch = async () => { calls++; return Response.json({}); };
  setTokenProviders({ appCheck: async () => { throw new Error("appCheck/fetch-status-error"); } });
  await assert.rejects(api.POST("/v1/endpoints/places/search", { body: { q: "museum" } }), AppCheckUnavailableError);
  setTokenProviders({ appCheck: async () => null });
  await assert.rejects(api.POST("/v1/endpoints/places/search", { body: { q: "museum" } }), AppCheckUnavailableError);
  assert.equal(calls, 0);
});
