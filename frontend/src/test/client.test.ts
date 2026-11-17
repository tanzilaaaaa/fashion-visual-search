import { AxiosError, AxiosHeaders } from "axios";
import { describe, expect, it } from "vitest";
import { ApiError, toApiError } from "../api/client";
import { altText } from "../lib/format";
import { validateImage } from "../components/ImageDropzone";

const axiosErr = (status?: number, data?: unknown) => {
  const e = new AxiosError("fail", status ? "ERR_BAD_RESPONSE" : "ERR_NETWORK");
  if (status) e.response = { status, data, statusText: "", headers: {}, config: { headers: new AxiosHeaders() } };
  return e;
};

describe("toApiError", () => {
  it("uses the API's error body", () => {
    const e = toApiError(axiosErr(413, { error: { code: "payload_too_large", message: "Image is larger than 8 MB." } }));
    expect(e).toBeInstanceOf(ApiError);
    expect(e.status).toBe(413);
    expect(e.code).toBe("payload_too_large");
    expect(e.message).toMatch(/8 MB/);
  });

  it("explains network failures", () => {
    expect(toApiError(axiosErr()).code).toBe("network_error");
  });
});

describe("helpers", () => {
  it("builds meaningful alt text", () => {
    expect(altText({ colour: "black", category: "long sleeve top", source: "user" })).toBe("Black long sleeve top — street photo");
    expect(altText({ colour: "multicolour", category: "skirt", source: "shop" })).toBe("Skirt — product photo");
  });

  it("validates image type and size", () => {
    expect(validateImage(new File(["x"], "a.png", { type: "image/png" }))).toBeNull();
    expect(validateImage(new File(["x"], "a.bmp", { type: "image/bmp" }))).toMatch(/unsupported/i);
    const big = new File([new Uint8Array(9 * 1024 * 1024)], "big.jpg", { type: "image/jpeg" });
    expect(validateImage(big)).toMatch(/larger than 8 MB/);
  });
});
