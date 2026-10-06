import { artifactArithmetic, classifyArtifact } from "./ovnisArtifactProvenance";

describe("OVNIS artifact provenance", () => {
  const ref = { artifactRefId: "artifact-1", locator: "https://example.test/a.pdf", expectedSourceId: "src-1" };

  it("keeps a locator-only artifact as reference-only", () => {
    expect(classifyArtifact(ref).state).toBe("REFERENCE_ONLY");
  });

  it("never promotes a reference into verified bytes without a manifestation", () => {
    expect(classifyArtifact(ref, null).state).not.toBe("VERIFIED");
  });

  it("requires immutable byte hash, size, acquisition time and authoritative binding", () => {
    const r = classifyArtifact(ref, {
      artifactRefId: ref.artifactRefId,
      byteSha256: null,
      byteSize: 100,
      acquiredAt: "2026-10-01T00:00:00Z",
      authoritativeBinding: true,
    });
    expect(r.state).toBe("ACQUIRED");
    expect(r.reasons).toContain("BYTE_HASH_MISSING");
  });

  it("verifies only a complete byte manifestation", () => {
    const r = classifyArtifact(ref, {
      artifactRefId: ref.artifactRefId,
      byteSha256: "a".repeat(64),
      byteSize: 100,
      acquiredAt: "2026-10-01T00:00:00Z",
      authoritativeBinding: true,
    });
    expect(r.state).toBe("VERIFIED");
  });

  it("preserves 244 references with zero verified bytes as 244 unresolved", () => {
    const refs = Array.from({ length: 244 }, (_, i) => ({ artifactRefId: `a-${i}`, locator: `https://example.test/${i}`, expectedSourceId: null }));
    const result = artifactArithmetic(refs, new Set());
    expect(result.references).toBe(244);
    expect(result.verified).toBe(0);
    expect(result.unresolved).toBe(244);
    expect(result.closes).toBeTrue();
  });
});
