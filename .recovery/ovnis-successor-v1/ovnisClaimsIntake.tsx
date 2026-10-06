export type ClaimState = "SUPPORTED" | "CONTRADICTED" | "SUPERSEDED" | "UNRESOLVED";

export interface ClaimEvidence {
  claimId: string;
  sourceManifestationIds: string[];
  sourceHashes: string[];
  assertedValue: string;
  supersedesClaimId?: string | null;
}

export function adjudicateClaims(claims: ClaimEvidence[]) {
  const byValue = new Map<string, ClaimEvidence[]>();
  for (const c of claims) {
    if (!c.sourceManifestationIds.length || c.sourceManifestationIds.length !== c.sourceHashes.length) continue;
    if (!c.sourceHashes.every(h => /^[a-f0-9]{64}$/i.test(h))) continue;
    byValue.set(c.assertedValue, [...(byValue.get(c.assertedValue) ?? []), c]);
  }

  const states = new Map<string, ClaimState>();
  for (const c of claims) states.set(c.claimId, "UNRESOLVED");
  const supportedGroups = [...byValue.values()].filter(group => group.length > 0);
  if (supportedGroups.length === 1) {
    for (const c of supportedGroups[0]) states.set(c.claimId, "SUPPORTED");
  } else if (supportedGroups.length > 1) {
    for (const group of supportedGroups) for (const c of group) states.set(c.claimId, "CONTRADICTED");
  }

  for (const c of claims) {
    if (!c.supersedesClaimId) continue;
    const prior = claims.find(x => x.claimId === c.supersedesClaimId);
    if (!prior) continue;
    if (states.get(c.claimId) === "SUPPORTED" && states.get(prior.claimId) === "SUPPORTED") {
      states.set(prior.claimId, "SUPERSEDED");
    }
  }
  return states;
}

export interface IntakeRecord {
  intakeId: string;
  sourceId: string;
  sourceSha256: string | null;
  stableExternalId: string | null;
  duplicateOfIntakeId: string | null;
}

export function validateGovernedIntake(records: IntakeRecord[]) {
  const seen = new Set<string>();
  const duplicateExternalIds = new Set<string>();
  const unresolved: string[] = [];
  for (const r of records) {
    if (!r.sourceSha256 || !/^[a-f0-9]{64}$/i.test(r.sourceSha256)) unresolved.push(r.intakeId);
    if (r.stableExternalId) {
      if (seen.has(r.stableExternalId) && !r.duplicateOfIntakeId) duplicateExternalIds.add(r.stableExternalId);
      seen.add(r.stableExternalId);
    }
  }
  return { pass: unresolved.length === 0 && duplicateExternalIds.size === 0, unresolved, duplicateExternalIds: [...duplicateExternalIds] };
}
