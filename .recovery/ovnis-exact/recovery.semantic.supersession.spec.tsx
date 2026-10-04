import { readFileSync } from "node:fs";

describe("OVNIS recovered GUI semantic supersession",()=>{
  const home=readFileSync("pages/_index.tsx","utf8");
  const cases=readFileSync("pages/cases.tsx","utf8");
  const custom=readFileSync("helpers/guiCustomization.tsx","utf8");
  it("routes the program mark Home without requiring one historical source location",()=>{
    expect(home+cases).toContain("OVNIS home");
    expect(home).toContain("/?lang=");
  });
  it("preserves provenance-first analyst language without infrastructure masquerade",()=>{
    expect(cases).toContain("provenance-first analyst registry");
    expect(home+cases).not.toContain("GitHub Actions");
    expect(home+cases).not.toContain("AUTHORITY_BLOCKED");
  });
  it("preserves pinned-snapshot and unresolved-replacement safeguards on the canonical cases surface",()=>{
    expect(cases).toContain("pinned snapshot");
    expect(cases).toContain("No nearest or name-based replacement was selected");
  });
  it("retains minimal Home tour and Customize controls",()=>{
    expect(home).toContain("Quick tour");
    expect(home).toContain("Customize");
  });
  it("persists preferences and locks required modules semantically",()=>{
    expect(custom).toContain("localStorage");
    expect(custom).toContain("required:true");
    expect(home).toContain("LOCKED · REQUIRED");
    expect(home).toContain("GUI_MODULES.find");
    expect(home).toContain("required)return");
  });
});
