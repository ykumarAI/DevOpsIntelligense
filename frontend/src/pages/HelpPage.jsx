import React, { useState } from "react";

function CodeBlock({ title, filename, language, code }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="code-block">
      <div className="code-block-head">
        <div className="code-block-title">
          {filename && <span className="code-file">{filename}</span>}
          {title && <span className="code-desc">{title}</span>}
          {language && <span className="code-lang">{language}</span>}
        </div>
        <button className="btn ghost sm" onClick={copy}>
          {copied ? "✓ Copied" : "Copy"}
        </button>
      </div>
      <pre className="code-block-body mono">
        <code>{code}</code>
      </pre>
    </div>
  );
}

const CI_TEMPLATE = `# .gitlab-ci.yml — DevOps Intelligence collector
# Runs a read-only AWS scan and publishes devops-report.json as an artifact.
# The dashboard reads that artifact via the GitLab API (no personal AWS access).

stages:
  - collect

collect:uat:
  stage: collect
  image: python:3.12-slim
  # OIDC token used to assume a read-only role in the target AWS account.
  id_tokens:
    GITLAB_OIDC_TOKEN:
      aud: https://gitlab.company.com
  variables:
    COLLECT_ENVIRONMENT: "UAT"
    AWS_DEFAULT_REGION: "us-east-1"
    AWS_ROLE_ARN: "arn:aws:iam::<ACCOUNT_ID>:role/devops-readonly"
    COLLECT_OUTPUT: "devops-report-uat.json"
    COLLECT_MAX: "25"
  script:
    - pip install --quiet boto3
    - python collect.py
  artifacts:
    when: always
    expire_in: 7 days
    paths:
      - devops-report-uat.json
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
    - if: '$CI_PIPELINE_SOURCE == "web"'
`;

const OIDC_TEMPLATE = `# AWS read-only role trust policy (assumed from GitLab CI via OIDC).
# Create an IAM OIDC provider for your GitLab URL first, then attach this trust
# policy to a role that has ONLY read-only (Describe*/List*/Get*) permissions.

{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/gitlab.company.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "gitlab.company.com:aud": "https://gitlab.company.com"
        },
        "StringLike": {
          "gitlab.company.com:sub": "project_path:platform/devops/collector:ref_type:branch:ref:main"
        }
      }
    }
  ]
}
`;

const TOKEN_STEPS = `# Personal / project access token for the dashboard to read artifacts.
# GitLab → Project → Settings → Access Tokens (or user Preferences → Access Tokens)
#
#   Name:   devops-dashboard-read
#   Role:   Reporter (or higher)
#   Scope:  read_api
#
# Copy the generated glpat-... value into the "Personal Access Token" field
# when adding a GitLab source below.
`;

export default function HelpPage({ onNavigate }) {
  return (
    <>
      <div className="header-row">
        <div>
          <div className="breadcrumb">Help // Getting Started</div>
          <h1>Help &amp; Setup Guide</h1>
          <div className="subtitle">
            Everything you need to connect environments and start monitoring —
            AWS accounts, individual instances, and GitLab-based collection.
          </div>
        </div>
      </div>

      {/* Overview */}
      <div className="help-section card">
        <h2>How this dashboard works</h2>
        <p className="help-p">
          DevOps Intelligence gives you a single view of environment health. There
          are two ways to feed it data:
        </p>
        <ul className="help-list">
          <li>
            <b>AWS Accounts (direct):</b> the dashboard connects to AWS using a
            profile, keys, or the default credential chain and scans resources
            itself. Best for accounts you have direct access to.
          </li>
          <li>
            <b>GitLab Sources (recommended for UAT/Prod):</b> a read-only CI job
            runs inside your pipeline, writes a <span className="mono">devops-report.json</span>{" "}
            artifact, and the dashboard just reads it over the GitLab API. No
            personal AWS access to production is required.
          </li>
        </ul>
      </div>

      {/* AWS Accounts */}
      <div className="help-section card">
        <h2>1 · Add an AWS account</h2>
        <ol className="help-steps">
          <li>
            Go to{" "}
            <button className="link-btn" onClick={() => onNavigate?.("accounts")}>
              Sources → AWS Accounts
            </button>{" "}
            and click <b>+ Add account</b>.
          </li>
          <li>
            Pick a <b>connection mode</b>:
            <ul className="help-list tight">
              <li>
                <b>Mock</b> — sample data, great for a first look with no
                credentials.
              </li>
              <li>
                <b>Profile</b> — use a named profile from your{" "}
                <span className="mono">~/.aws/credentials</span> file.
              </li>
              <li>
                <b>Keys</b> — paste an access key / secret (and optional session
                token). Use read-only credentials.
              </li>
            </ul>
          </li>
          <li>
            Set the <b>region</b> (e.g. <span className="mono">us-east-1</span>) and
            save.
          </li>
        </ol>
      </div>

      {/* Instances / Resources */}
      <div className="help-section card">
        <h2>2 · Add instances &amp; monitored resources</h2>
        <ol className="help-steps">
          <li>
            Open{" "}
            <button className="link-btn" onClick={() => onNavigate?.("resources")}>
              Operations → Monitored Resources
            </button>
            .
          </li>
          <li>
            Click <b>+ Add resource</b>, choose the account, then the resource{" "}
            <b>type</b> (EC2 instance, ECS service, RDS, S3, etc.).
          </li>
          <li>
            Enter the <b>identifier</b> (for example an EC2 instance id like{" "}
            <span className="mono">i-0abc123</span>) and a friendly display name.
          </li>
          <li>
            Save — the dashboard begins polling status on the auto-refresh
            interval set in{" "}
            <button className="link-btn" onClick={() => onNavigate?.("settings")}>
              Settings
            </button>
            .
          </li>
        </ol>
      </div>

      {/* GitLab */}
      <div className="help-section card">
        <h2>3 · Set up a GitLab source</h2>
        <p className="help-p">
          Use these templates to stand up the collector pipeline. Copy each one
          into your collector repository, adjust the placeholders (
          <span className="mono">&lt;ACCOUNT_ID&gt;</span>, region, environment,
          GitLab URL), then commit and run the pipeline.
        </p>

        <h3 className="help-h3">a. Read-only AWS role (OIDC trust policy)</h3>
        <CodeBlock
          filename="devops-readonly-trust.json"
          language="json"
          code={OIDC_TEMPLATE}
        />

        <h3 className="help-h3">b. Pipeline job</h3>
        <CodeBlock
          filename=".gitlab-ci.yml"
          language="yaml"
          code={CI_TEMPLATE}
        />

        <h3 className="help-h3">c. Collector script</h3>
        <p className="help-p tight">
          A ready-to-use read-only collector ships with this project at{" "}
          <span className="mono">examples/gitlab-collector/collect.py</span>. Drop
          it into your repo next to the <span className="mono">.gitlab-ci.yml</span>{" "}
          above. It emits the exact <span className="mono">devops-report.json</span>{" "}
          schema the dashboard expects.
        </p>

        <h3 className="help-h3">d. Access token for the dashboard</h3>
        <CodeBlock
          filename="access-token.txt"
          language="text"
          code={TOKEN_STEPS}
        />

        <h3 className="help-h3">e. Register the source here</h3>
        <ol className="help-steps">
          <li>
            Go to{" "}
            <button className="link-btn" onClick={() => onNavigate?.("gitlab")}>
              Sources → GitLab Sources
            </button>{" "}
            and click <b>+ Add GitLab source</b>.
          </li>
          <li>
            Fill in the fields to match your pipeline:
            <ul className="help-list tight">
              <li>
                <b>GitLab base URL</b> —{" "}
                <span className="mono">https://gitlab.company.com</span>
              </li>
              <li>
                <b>Project</b> — numeric ID or path (
                <span className="mono">platform/devops/collector</span>)
              </li>
              <li>
                <b>Ref</b> — branch or tag the pipeline runs on (
                <span className="mono">main</span>)
              </li>
              <li>
                <b>Collector job name</b> — must match the job (
                <span className="mono">collect:uat</span>)
              </li>
              <li>
                <b>Artifact path</b> —{" "}
                <span className="mono">devops-report-uat.json</span>
              </li>
              <li>
                <b>Personal Access Token</b> — the{" "}
                <span className="mono">glpat-...</span> value from step d
              </li>
            </ul>
          </li>
          <li>
            Click <b>Test</b> to verify the dashboard can fetch the artifact, then{" "}
            <b>Save</b>.
          </li>
        </ol>
      </div>

      {/* Troubleshooting */}
      <div className="help-section card">
        <h2>Troubleshooting</h2>
        <ul className="help-list">
          <li>
            <b>Test fails with 404:</b> confirm the job name, artifact path, and
            ref exactly match your pipeline, and that the job has run at least once
            successfully.
          </li>
          <li>
            <b>401 / 403:</b> the access token is missing the{" "}
            <span className="mono">read_api</span> scope or lacks access to the
            project.
          </li>
          <li>
            <b>Empty resources:</b> the collector ran but found nothing — check the
            role region and that the read-only role can Describe/List the services.
          </li>
          <li>
            <b>AWS account shows errors:</b> verify the profile/keys are valid and
            the region is correct in{" "}
            <button className="link-btn" onClick={() => onNavigate?.("accounts")}>
              AWS Accounts
            </button>
            .
          </li>
        </ul>
      </div>
    </>
  );
}
