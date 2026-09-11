/**
 * Scope Creep Sentinel - dashboard frontend.
 *
 * Vanilla JS, no build step.
 * Talks to the FastAPI backend at the same origin.
 */

const CLASSIFICATION_BADGE = {
  IN_SCOPE: {
    text: "In scope",
    className: "badge-in-scope",
  },

  GRAY_AREA: {
    text: "Gray area",
    className: "badge-gray-area",
  },

  OUT_OF_SCOPE: {
    text: "Out of scope",
    className: "badge-out-of-scope",
  },
};

const DECISION_LABEL = {
  BILL_IT: "Billed",
  NEGOTIATE_IT: "Negotiated",
  DECLINE_IT: "Declined",
};

let currentAnalysis = null;


document.addEventListener("DOMContentLoaded", () => {
  loadProject();
  loadHistory();

  document
    .getElementById("request-form")
    .addEventListener("submit", onAnalyzeSubmit);

  document
    .getElementById("email-form")
    .addEventListener("submit", onEmailSubmit);

  document
    .getElementById("gmail-check-btn")
    .addEventListener("click", onGmailCheck);

  document
    .querySelectorAll("[data-decision]")
    .forEach((btn) => {
      btn.addEventListener("click", () =>
        onDecisionClick(btn.dataset.decision)
      );
    });
});


/* ====================================================================== */
/* Project + history                                                      */
/* ====================================================================== */

async function loadProject() {
  try {
    const project = await getJSON("/api/project");
    renderProject(project);
  } catch (err) {
    console.error(
      "Failed to load project overview:",
      err
    );
  }
}


async function loadHistory() {
  try {
    const history = await getJSON("/api/history");

    renderHistory(history);
    renderStatStrip(history.summary);
  } catch (err) {
    console.error(
      "Failed to load history:",
      err
    );
  }
}


function renderProject(project) {
  document.getElementById(
    "sow-project-name"
  ).textContent = project.project_name;

  document.getElementById(
    "sow-hourly-rate"
  ).textContent =
    formatCurrency(project.hourly_rate) +
    " / hour";

  document.getElementById(
    "sow-revisions-text"
  ).textContent =
    `${project.revisions_used} of ${project.revision_limit} used`;

  const pct =
    project.revision_limit > 0
      ? Math.min(
          100,
          (project.revisions_used /
            project.revision_limit) *
            100
        )
      : 0;

  document.getElementById(
    "revision-meter-fill"
  ).style.width = `${pct}%`;

  fillList(
    "sow-included",
    project.included_items
  );

  fillList(
    "sow-excluded",
    project.excluded_items
  );
}


function renderStatStrip(summary) {
  document.getElementById(
    "stat-hours"
  ).textContent =
    `${summary.accumulated_unbilled_hours}h`;

  document.getElementById(
    "stat-cost"
  ).textContent =
    formatCurrency(
      summary.accumulated_unbilled_cost
    );

  document.getElementById(
    "stat-count"
  ).textContent =
    summary.scope_creep_requests;

  document.getElementById(
    "stat-creep-hours"
  ).textContent =
    `${summary.total_scope_creep_hours}h`;

  document.getElementById(
    "stat-creep-cost"
  ).textContent =
    formatCurrency(
      summary.total_scope_creep_cost
    );
}


function fillList(elementId, items) {
  const el = document.getElementById(
    elementId
  );

  el.innerHTML = "";

  if (!items || items.length === 0) {
    el.innerHTML = "<li>(none)</li>";
    return;
  }

  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item;
    el.appendChild(li);
  }
}


/* ====================================================================== */
/* Manual request                                                        */
/* ====================================================================== */

async function onAnalyzeSubmit(event) {
  event.preventDefault();

  const textarea =
    document.getElementById("request-text");

  const requestText =
    textarea.value.trim();

  const errorEl =
    document.getElementById("request-error");

  const analyzeBtn =
    document.getElementById("analyze-btn");

  errorEl.hidden = true;

  if (!requestText) {
    return;
  }

  setResultLoading();

  analyzeBtn.disabled = true;
  analyzeBtn.textContent =
    "Analyzing…";

  try {
    const analysis = await postJSON(
      "/api/requests",
      {
        request_text: requestText,
      }
    );

    currentAnalysis = analysis;

    renderResult(
      analysis,
      {
        source: "Manual request",
      }
    );

    await loadHistory();
    await loadProject();
  } catch (err) {
    console.error(
      "Analyze failed:",
      err
    );

    errorEl.textContent =
      getFriendlyError(
        err,
        "Could not analyze that request."
      );

    errorEl.hidden = false;

    showResultEmpty();
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent =
      "Analyze request";
  }
}


/* ====================================================================== */
/* Simulated email                                                        */
/* ====================================================================== */

async function onEmailSubmit(event) {
  event.preventDefault();

  const sender =
    document.getElementById(
      "email-sender"
    ).value.trim();

  const subject =
    document.getElementById(
      "email-subject"
    ).value.trim();

  const body =
    document.getElementById(
      "email-body"
    ).value.trim();

  const errorEl =
    document.getElementById(
      "email-error"
    );

  const emailBtn =
    document.getElementById(
      "email-analyze-btn"
    );

  errorEl.hidden = true;

  if (!sender || !subject || !body) {
    errorEl.textContent =
      "Please enter the client email, subject, and email body.";

    errorEl.hidden = false;
    return;
  }

  setResultLoading();

  emailBtn.disabled = true;
  emailBtn.textContent =
    "Processing email…";

  try {
    const analysis = await postJSON(
      "/api/emails",
      {
        sender,
        subject,
        body,
      }
    );

    currentAnalysis = analysis;

    renderResult(
      analysis,
      {
        source: "Client email",
        sender,
        subject,
      }
    );

    await loadHistory();
    await loadProject();
  } catch (err) {
    console.error(
      "Email processing failed:",
      err
    );

    errorEl.textContent =
      getFriendlyError(
        err,
        "Could not process the simulated client email."
      );

    errorEl.hidden = false;

    showResultEmpty();
  } finally {
    emailBtn.disabled = false;
    emailBtn.textContent =
      "Process simulated email";
  }
}


/* ====================================================================== */
/* Real Gmail                                                            */
/* ====================================================================== */

async function onGmailCheck() {
  const button =
    document.getElementById(
      "gmail-check-btn"
    );

  const errorEl =
    document.getElementById(
      "gmail-error"
    );

  const statusEl =
    document.getElementById(
      "gmail-status"
    );

  errorEl.hidden = true;
  statusEl.hidden = false;

  button.disabled = true;
  button.textContent =
    "Checking Gmail…";

  statusEl.textContent =
    "Checking the connected inbox and screening candidate emails…";

  setResultLoading();

  try {
    const result =
      await postJSON(
        "/api/gmail/check",
        {}
      );

    const processed =
      result.processed_client_requests || 0;

    const checked =
      result.candidate_emails_checked || 0;

    const skipped =
      result.skipped_non_client_emails || 0;

    if (
      processed > 0 &&
      result.results &&
      result.results.length > 0
    ) {
      const analysis =
        result.results[0];

      currentAnalysis = analysis;

      renderResult(
        analysis,
        {
          source: "Connected Gmail",
          sender:
            analysis.request_text
              ?.split("\n")[0]
              ?.replace(
                /^Subject:\s*/i,
                ""
              ) || "",
        }
      );

      statusEl.textContent =
        `Found a client request after checking ${checked} candidate email(s).`;

      await loadHistory();
      await loadProject();

      return;
    }

    showResultEmpty();

    statusEl.textContent =
      `No client request found. Checked ${checked} candidate email(s) and skipped ${skipped} non-client email(s).`;

    await loadHistory();
    await loadProject();

  } catch (err) {
    console.error(
      "Gmail check failed:",
      err
    );

    showResultEmpty();

    errorEl.textContent =
      getFriendlyError(
        err,
        "Could not check Gmail."
      );

    errorEl.hidden = false;

    statusEl.textContent =
      "Gmail check did not complete.";
  } finally {
    button.disabled = false;
    button.textContent =
      "Check Gmail for client requests";
  }
}


/* ====================================================================== */
/* Result rendering                                                       */
/* ====================================================================== */

function setResultLoading() {
  const resultEl =
    document.getElementById("result");

  const emptyEl =
    document.getElementById("result-empty");

  resultEl.hidden = false;
  emptyEl.hidden = true;

  document.getElementById(
    "result-source"
  ).hidden = true;

  document.getElementById(
    "classification-badge"
  ).textContent =
    "Analyzing…";

  document.getElementById(
    "classification-badge"
  ).className =
    "badge";

  document.getElementById(
    "risk-tag"
  ).textContent = "";

  document.getElementById(
    "reasoning-text"
  ).textContent =
    "The Sentinel is analyzing the request against the Statement of Work…";

  document.getElementById(
    "matched-sow-item"
  ).textContent =
    "Analyzing…";

  document.getElementById(
    "decision-requirement"
  ).textContent =
    "Analyzing…";

  document.getElementById(
    "impact-hours"
  ).textContent = "—";

  document.getElementById(
    "impact-cost"
  ).textContent = "—";

  document.getElementById(
    "decision-reasoning"
  ).hidden = true;

  document.getElementById(
    "in-scope-note"
  ).hidden = true;

  document.getElementById(
    "decision-block"
  ).hidden = true;

  document.getElementById(
    "decision-confirmation"
  ).hidden = true;
}


function showResultEmpty() {
  document.getElementById(
    "result"
  ).hidden = true;

  document.getElementById(
    "result-empty"
  ).hidden = false;
}


function renderResult(
  analysis,
  metadata = null
) {
  const resultEl =
    document.getElementById("result");

  const emptyEl =
    document.getElementById("result-empty");

  resultEl.hidden = false;
  emptyEl.hidden = true;


  /* ------------------------------------------------------------------ */
  /* Source                                                             */
  /* ------------------------------------------------------------------ */

  const sourceEl =
    document.getElementById("result-source");

  const sourceValueEl =
    document.getElementById(
      "result-source-value"
    );

  sourceEl.hidden = false;

  if (
    metadata &&
    metadata.source === "Client email"
  ) {
    sourceValueEl.textContent =
      [
        metadata.source,
        metadata.sender,
        metadata.subject,
      ]
        .filter(Boolean)
        .join(" · ");
  } else if (
    metadata &&
    metadata.source === "Connected Gmail"
  ) {
    sourceValueEl.textContent =
      "Connected Gmail · Real inbox";
  } else {
    sourceValueEl.textContent =
      "Manual request";
  }


  /* ------------------------------------------------------------------ */
  /* Classification                                                     */
  /* ------------------------------------------------------------------ */

  const badgeInfo =
    CLASSIFICATION_BADGE[
      analysis.classification
    ] || {
      text: analysis.classification,
      className: "",
    };

  const badgeEl =
    document.getElementById(
      "classification-badge"
    );

  badgeEl.textContent =
    badgeInfo.text;

  badgeEl.className =
    `badge ${badgeInfo.className}`;


  /* ------------------------------------------------------------------ */
  /* Risk                                                               */
  /* ------------------------------------------------------------------ */

  document.getElementById(
    "risk-tag"
  ).textContent =
    `${analysis.risk_level.toLowerCase()} risk`;


  /* ------------------------------------------------------------------ */
  /* Main reasoning                                                     */
  /* ------------------------------------------------------------------ */

  document.getElementById(
    "reasoning-text"
  ).textContent =
    analysis.reasoning || "—";


  /* ------------------------------------------------------------------ */
  /* SOW evidence                                                       */
  /* ------------------------------------------------------------------ */

  document.getElementById(
    "matched-sow-item"
  ).textContent =
    analysis.matched_sow_item ||
    "No direct SOW item matched";


  document.getElementById(
    "decision-requirement"
  ).textContent =
    analysis.requires_decision
      ? "Human decision required"
      : "No decision required";


  /* ------------------------------------------------------------------ */
  /* Effort + cost                                                      */
  /* ------------------------------------------------------------------ */

  document.getElementById(
    "impact-hours"
  ).textContent =
    `${analysis.estimated_hours}h`;

  document.getElementById(
    "impact-cost"
  ).textContent =
    formatCurrency(
      analysis.estimated_cost
    );


  /* ------------------------------------------------------------------ */
  /* Decision reasoning                                                 */
  /* ------------------------------------------------------------------ */

  const decisionReasoningEl =
    document.getElementById(
      "decision-reasoning"
    );

  const decisionReasoningTextEl =
    document.getElementById(
      "decision-reasoning-text"
    );

  if (
    analysis.decision_reasoning &&
    analysis.requires_decision
  ) {
    decisionReasoningEl.hidden =
      false;

    decisionReasoningTextEl.textContent =
      analysis.decision_reasoning;
  } else {
    decisionReasoningEl.hidden =
      true;

    decisionReasoningTextEl.textContent =
      "";
  }


  /* ------------------------------------------------------------------ */
  /* Decision state                                                     */
  /* ------------------------------------------------------------------ */

  const inScopeNote =
    document.getElementById(
      "in-scope-note"
    );

  const decisionBlock =
    document.getElementById(
      "decision-block"
    );

  const confirmation =
    document.getElementById(
      "decision-confirmation"
    );

  confirmation.hidden = true;

  if (!analysis.requires_decision) {
    inScopeNote.hidden = false;
    decisionBlock.hidden = true;
    return;
  }

  inScopeNote.hidden = true;
  decisionBlock.hidden = false;


  /* ------------------------------------------------------------------ */
  /* Generated messages                                                 */
  /* ------------------------------------------------------------------ */

  if (analysis.messages) {
    document.getElementById(
      "message-bill"
    ).textContent =
      analysis.messages.bill_it || "";

    document.getElementById(
      "message-negotiate"
    ).textContent =
      analysis.messages.negotiate_it || "";

    document.getElementById(
      "message-decline"
    ).textContent =
      analysis.messages.decline_it || "";
  }
}


/* ====================================================================== */
/* Human decision                                                         */
/* ====================================================================== */

async function onDecisionClick(
  decision
) {
  if (!currentAnalysis) {
    return;
  }

  const buttons =
    document.querySelectorAll(
      "[data-decision]"
    );

  buttons.forEach((button) => {
    button.disabled = true;
  });

  try {
    const result =
      await postJSON(
        `/api/requests/${currentAnalysis.id}/decision`,
        {
          decision,
        }
      );

    document.getElementById(
      "decision-block"
    ).hidden = true;

    document.getElementById(
      "decision-confirmation"
    ).hidden = false;

    document.getElementById(
      "confirmation-text"
    ).textContent =
      result.sent_message;

    document.getElementById(
      "request-text"
    ).value = "";

    document.getElementById(
      "email-subject"
    ).value = "";

    document.getElementById(
      "email-body"
    ).value = "";

    currentAnalysis = null;

    await loadHistory();
    await loadProject();

  } catch (err) {
    console.error(
      "Decision failed:",
      err
    );

    alert(
      getFriendlyError(
        err,
        "Could not save that decision."
      )
    );
  } finally {
    buttons.forEach((button) => {
      button.disabled = false;
    });
  }
}


/* ====================================================================== */
/* History                                                                */
/* ====================================================================== */

function renderHistory(history) {
  const body =
    document.getElementById(
      "history-body"
    );

  body.innerHTML = "";

  if (
    !history.records ||
    history.records.length === 0
  ) {
    body.innerHTML =
      '<tr><td colspan="8" class="history-empty">No requests logged yet.</td></tr>';

    return;
  }

  const records =
    [...history.records].reverse();

  for (const record of records) {
    const tr =
      document.createElement("tr");

    const badgeInfo =
      CLASSIFICATION_BADGE[
        record.classification
      ] || {
        text: record.classification,
        className: "",
      };

    const decisionText =
      record.user_decision
        ? DECISION_LABEL[
            record.user_decision
          ]
        : "—";

    const sourceText =
      record.source === "email"
        ? "Email"
        : "Manual";

    const clientText =
      record.sender ||
      "—";

    tr.innerHTML = `
      <td>
        ${formatTimestamp(record.timestamp)}
      </td>

      <td>
        <span class="source-badge">
          ${escapeHtml(sourceText)}
        </span>
      </td>

      <td>
        ${escapeHtml(clientText)}
      </td>

      <td>
        ${escapeHtml(record.request_text)}
      </td>

      <td>
        <span class="badge ${badgeInfo.className}">
          ${badgeInfo.text}
        </span>
      </td>

      <td>
        ${record.estimated_hours}h
      </td>

      <td>
        ${formatCurrency(record.estimated_cost)}
      </td>

      <td>
        ${escapeHtml(decisionText)}
      </td>
    `;

    body.appendChild(tr);
  }
}


/* ====================================================================== */
/* Utilities                                                              */
/* ====================================================================== */

function formatCurrency(amount) {
  return new Intl.NumberFormat(
    "en-US",
    {
      style: "currency",
      currency: "USD",
    }
  ).format(amount);
}


function formatTimestamp(
  isoString
) {
  const date =
    new Date(isoString);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return isoString;
  }

  return date.toLocaleString(
    undefined,
    {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }
  );
}


function escapeHtml(text) {
  const div =
    document.createElement(
      "div"
    );

  div.textContent =
    text ?? "";

  return div.innerHTML;
}


function getFriendlyError(
  error,
  fallback
) {
  if (
    error &&
    error.message
  ) {
    return error.message;
  }

  return fallback;
}


async function getJSON(path) {
  const res =
    await fetch(path);

  if (!res.ok) {
    throw new Error(
      `GET ${path} failed: ${res.status}`
    );
  }

  return res.json();
}


async function postJSON(
  path,
  body
) {
  const res =
    await fetch(
      path,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify(body),
      }
    );

  if (!res.ok) {
    let detail =
      `POST ${path} failed: ${res.status}`;

    try {
      const errorBody =
        await res.json();

      if (errorBody.detail) {
        detail =
          `${detail}: ${errorBody.detail}`;
      }
    } catch (_) {
      // Keep the default error.
    }

    throw new Error(detail);
  }

  return res.json();
}