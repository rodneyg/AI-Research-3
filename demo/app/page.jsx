import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Study } from "./study";

export default function Page() {
  const repositorySummary = resolve("../results/summary.json");
  const summaryPath = existsSync(repositorySummary) ? repositorySummary : resolve("results/summary.json");
  const summary = JSON.parse(readFileSync(summaryPath, "utf8"));
  return <Study summary={summary} />;
}
