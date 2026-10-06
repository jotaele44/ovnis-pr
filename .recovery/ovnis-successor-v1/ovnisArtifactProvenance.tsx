export type ArtifactState = "REFERENCE_ONLY" | "ACQUIRED" | "VERIFIED" | "BLOCKED";

export interface ArtifactReference {
  artifactRefId: string;
  locator: string | null;
  expectedSourceId: string | null;
}

export interface ArtifactManifestation {
  artifactRefId: string;
  byteSha256: string | null;
  byteSize: number | null;
  acquiredAt: string | null;
  authoritativeBinding: boolean;
}

export function classifyArtifact(
  ref: ArtifactReference,
  manifestation?: ArtifactManifestation | null
): { state: ArtifactState; reasons: string[] } {
  const reasons: string[] = [];
  if (!ref.artifactRefId) reasons.push("REFERENCE_ID_MISSING");
  if (!ref.locator) reasons.push("LOCATOR_MISSING");
  if (!manifestation) {
    return { state: ref.locator ? "REFERENCE_ONLY" : "BLOCKED", reasons };
  }
  if (!manifestation.byteSha256 || !/^[a-f0-9]{64}$/i.test(manifestation.byteSha256)) reasons.push("BYTE_HASH_MISSING");
  if (manifestation.byteSize === null || manifestation.byteSize < 0) reasons.push("BYTE_SIZE_MISSING");
  if (!manifestation.acquiredAt) reasons.push("ACQUIRED_AT_MISSING");
  if (!manifestation.authoritativeBinding) reasons.push("AUTHORITATIVE_BINDING_MISSING");
  if (reasons.length) return { state: "ACQUIRED", reasons };
  return { state: "VERIFIED", reasons };
}

export function artifactArithmetic(references: ArtifactReference[], verifiedIds: Set<string>) {
  const verified = references.filter(r => verifiedIds.has(r.artifactRefId)).length;
  return {
    references: references.length,
    verified,
    unresolved: references.length - verified,
    closes: references.length === verified + (references.length - verified),
  };
}
