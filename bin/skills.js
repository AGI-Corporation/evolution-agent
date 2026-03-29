#!/usr/bin/env node
// bin/skills.js
// Node.js shim that forwards `npx skills <command>` to the Python skills CLI.
//
// Usage:
//   npx skills add bitrefill/agents
//   npx skills list
//   npx skills info bitrefill/agents

"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

// Resolve project root (one directory above bin/)
const projectRoot = path.resolve(__dirname, "..");

// Forward all CLI arguments to `python -m skills`
const args = process.argv.slice(2);
const result = spawnSync("python", ["-m", "skills", ...args], {
  cwd: projectRoot,
  stdio: "inherit",
  env: process.env,
});

if (result.error) {
  console.error(
    "[skills] Failed to launch Python skills CLI:",
    result.error.message
  );
  console.error(
    "Ensure Python 3 is installed and the evolution-agent dependencies are set up."
  );
  process.exit(1);
}

process.exit(result.status ?? 0);
