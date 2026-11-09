import { describe, expect, it } from "vitest";
import { keyStatusLine } from "./AiSettingsPage";

describe("keyStatusLine", () => {
  it("shows only the last 4 characters and where the key is kept", () => {
    expect(keyStatusLine({ configured: true, source: "app", can_manage: true, hint: "abcd", updated_at: null })).toBe("Key set (…abcd), saved in the app.");
    expect(keyStatusLine({ configured: true, source: "server", can_manage: true, hint: "wxyz", updated_at: null })).toBe("Key set (…wxyz), saved on the server.");
    expect(keyStatusLine({ configured: true, source: "server", can_manage: false, hint: null, updated_at: null })).toBe("Key set, saved on the server.");
    expect(keyStatusLine({ configured: false, source: "none", can_manage: true, hint: null, updated_at: null })).toMatch(/No key yet/);
  });
});
