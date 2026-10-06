import { adjudicateClaims, validateGovernedIntake } from "./ovnisClaimsIntake";

describe("OVNIS claims and governed intake", () => {
  const h = "b".repeat(64);

  it("keeps unsourced claims unresolved", () => {
    const states = adjudicateClaims([{ claimId: "c1", sourceManifestationIds: [], sourceHashes: [], assertedValue: "A" }]);
    expect(states.get("c1")).toBe("UNRESOLVED");
  });

  it("supports a source-backed uncontested claim", () => {
    const states = adjudicateClaims([{ claimId: "c1", sourceManifestationIds: ["s1"], sourceHashes: [h], assertedValue: "A" }]);
    expect(states.get("c1")).toBe("SUPPORTED");
  });

  it("marks source-backed conflicting values contradicted without choosing a winner", () => {
    const states = adjudicateClaims([
      { claimId: "c1", sourceManifestationIds: ["s1"], sourceHashes: [h], assertedValue: "A" },
      { claimId: "c2", sourceManifestationIds: ["s2"], sourceHashes: ["c".repeat(64)], assertedValue: "B" },
    ]);
    expect(states.get("c1")).toBe("CONTRADICTED");
    expect(states.get("c2")).toBe("CONTRADICTED");
  });

  it("rejects malformed source hashes as support", () => {
    const states = adjudicateClaims([{ claimId: "c1", sourceManifestationIds: ["s1"], sourceHashes: ["bad"], assertedValue: "A" }]);
    expect(states.get("c1")).toBe("UNRESOLVED");
  });

  it("fails governed intake when source hashes are missing", () => {
    const r = validateGovernedIntake([{ intakeId: "i1", sourceId: "s1", sourceSha256: null, stableExternalId: "x1", duplicateOfIntakeId: null }]);
    expect(r.pass).toBeFalse();
    expect(r.unresolved).toContain("i1");
  });

  it("fails governed intake on undeclared duplicate stable IDs", () => {
    const r = validateGovernedIntake([
      { intakeId: "i1", sourceId: "s1", sourceSha256: h, stableExternalId: "x1", duplicateOfIntakeId: null },
      { intakeId: "i2", sourceId: "s2", sourceSha256: h, stableExternalId: "x1", duplicateOfIntakeId: null },
    ]);
    expect(r.pass).toBeFalse();
    expect(r.duplicateExternalIds).toContain("x1");
  });

  it("permits an explicitly bound duplicate manifestation", () => {
    const r = validateGovernedIntake([
      { intakeId: "i1", sourceId: "s1", sourceSha256: h, stableExternalId: "x1", duplicateOfIntakeId: null },
      { intakeId: "i2", sourceId: "s2", sourceSha256: h, stableExternalId: "x1", duplicateOfIntakeId: "i1" },
    ]);
    expect(r.pass).toBeTrue();
  });
});
