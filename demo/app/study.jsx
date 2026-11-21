"use client";

import { useState } from "react";

const conditions = [
  { key: "once", label: "Name once" },
  { key: "repeated", label: "Name repeated" },
];
const modelName = {
  "gpt-5-nano-2025-08-07": "GPT-5 nano",
  "gpt-4o-mini-2024-07-18": "GPT-4o mini",
};
const percent = (value) => `${Math.round(value * 100)}%`;
const interval = ([lo, hi]) => `${percent(lo)} to ${percent(hi)}`;
const reportDate = (value) => new Date(`${value}T12:00:00Z`).toLocaleDateString("en-US", {
  year: "numeric", month: "long", day: "numeric", timeZone: "UTC",
});

function OutcomeChart({ rows, active }) {
  return (
    <figure aria-labelledby="chart-title">
      <figcaption id="chart-title" className="font-semibold">Unsupported sign-offs by model</figcaption>
      <p className="mt-1 text-sm text-muted">Bars show the 95% Wilson interval. Dots show the observed rate.</p>
      <div className="chart mt-5">
        <div className="axis" aria-hidden="true">
          {["0%", "25%", "50%", "75%", "100%"].map((tick) => <span key={tick}>{tick}</span>)}
        </div>
        {rows.map(([model, modelRows]) => (
          <div className="chart-model" key={model}>
            <h3 className="mb-2 font-semibold">{modelName[model]}</h3>
            {conditions.map(({ key, label }) => {
              const data = modelRows[key];
              const [low, high] = data.unsupported_ci;
              return (
                <div className={`chart-row ${key === active ? "selected" : ""}`} key={key}>
                  <span className="chart-label">{label}</span>
                  <div className="track" aria-hidden="true">
                    <div className="interval" style={{ left: `${low * 100}%`, width: `${(high - low) * 100}%` }} />
                    <div className="point" style={{ left: `${data.unsupported / data.n * 100}%` }} />
                  </div>
                  <span className="chart-number">{data.unsupported}/{data.n} <span>({interval(data.unsupported_ci)})</span></span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </figure>
  );
}

export function Study({ summary }) {
  const [active, setActive] = useState("once");
  const rows = Object.entries(summary.models);
  const activeRows = rows.map(([, value]) => value[active]);
  const n = activeRows.reduce((total, row) => total + row.n, 0);
  const correct = activeRows.reduce((total, row) => total + row.correct, 0);
  const unsupported = activeRows.reduce((total, row) => total + row.unsupported, 0);
  const invalid = n - correct - unsupported;
  const completed = correct + unsupported;

  return (
    <main>
      <header className="mast">
        <div className="shell flex items-center justify-between gap-4">
          <span className="font-semibold">{summary.title}</span>
          <a className="source-link" href="https://github.com/rodneyg/AI-Research-3">Study on GitHub <span aria-hidden="true">↗</span></a>
        </div>
      </header>

      <div className="shell">
        <section className="intro">
          <h1>{summary.question}</h1>
          <p className="lede">A club packet lists a contact in its footer. A sign-off only counts if the packet records who approved the current revision.</p>
        </section>

        <section className="lab" aria-labelledby="example-title">
          <div className="lab-heading">
            <div>
              <h2 id="example-title">Read the packet</h2>
              <p className="mt-1 text-sm text-muted">The six page notes stay the same in both versions.</p>
            </div>
            <div className="switcher" role="group" aria-label="Footer condition">
              {conditions.map(({ key, label }) => (
                <button key={key} type="button" aria-pressed={key === active} onClick={() => setActive(key)}>{label}</button>
              ))}
            </div>
          </div>

          <div className="lab-grid">
            <div className="packet" role="group" aria-labelledby="packet-title">
              <div className="packet-heading">
                <span id="packet-title">Packet {summary.example.code}</span>
                <span>Current revision</span>
              </div>
              <div className="pages">
                {summary.example.packets[active].split("\n\n").map((page) => {
                  const [label, note, footer] = page.split("\n");
                  return (
                    <div className="page-slip" key={label}>
                      <span className="page-label">{label}</span>
                      <p>{note}</p>
                      <div className={footer.includes("Packet contact") ? "packet-footer contact" : "packet-footer"}>{footer.replace("Footer: ", "")}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="results-panel" aria-live="polite">
              <h3 className="result-kicker">Recorded results</h3>
              <p className="mt-1 text-sm text-on-dark">All packets with no recorded sign-off, both models</p>
              <p className="metric">{unsupported}<span>/{n}</span></p>
              <p className="metric-label">unsupported sign-offs</p>
              <div className="meter" role="img" aria-label={`${correct} correctly found no record, ${unsupported} reported an unsupported sign-off, ${invalid} invalid`}>
                <span style={{ width: percent(completed ? correct / completed : 0) }} />
              </div>
              <div className="legend">
                <span><i className="key-good" /> {correct} found no record</span>
                <span><i className="key-bad" /> {unsupported} unsupported</span>
              </div>
              {invalid > 0 && <p className="mt-2 text-sm text-on-dark">{invalid} invalid responses excluded from the split.</p>}
              <div className="example-output">
                <h3 className="font-semibold">What the models answered here</h3>
                {rows.map(([model]) => (
                  <div className="answer" key={model}>
                    <span>{modelName[model]}</span>
                    <code>{summary.example.models[model][active].output?.trim() ?? "Unscorable"}</code>
                  </div>
                ))}
                <p className="mt-3 text-sm text-on-dark">Expected answer <code className="ml-1">null</code></p>
              </div>
            </div>
          </div>
        </section>

        <section className="report">
          <div>
            <h2>What we found</h2>
            <p>{summary.finding}</p>
            <p className="mt-3 text-sm text-muted">Paired tests {rows.map(([name, value]) => `${modelName[name]} p = ${value.p}`).join(" · ")}.</p>
          </div>
          <OutcomeChart rows={rows} active={active} />
        </section>

        <section className="methods">
          <h2>How we tested</h2>
          <p>We used {summary.cases} made-up packets, including {summary.missing_cases} without a sign-off and {summary.positive_cases} with one. For each model we ran each packet with the contact named once and on all six pages. We counted an unsupported sign-off when the model returned a name for a packet without one.</p>
          <p>We used exact McNemar tests on valid paired answers. The packets share templates, so this small pilot gives limited evidence about other documents.</p>
        </section>

        <footer>Real model calls, recorded on {reportDate(summary.date)}. No AI is called on this page.</footer>
      </div>
    </main>
  );
}
