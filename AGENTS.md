# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## Project

PythonBridgeQuantower is a Quantower Strategy that streams trade prints (last
prices) out of Quantower over a localhost TCP socket as newline-delimited JSON.
A companion Python TUI (not in the C# project) reads the stream and renders a
live scrolling time-and-sales tape. The strategy targets .NET 8.0, x64. See
`specs/01-socket-bridge.md` for the full specification.

## Build

```
dotnet build PythonBridgeQuantower/PythonBridgeQuantower.csproj -c Release
```

The `.csproj` resolves the Quantower SDK reference dynamically by scanning
`C:\Quantower\TradingPlatform\v*` and picking the lexicographically last `v*`
directory. Override `QT_Root` if Quantower is installed elsewhere.
`<Private>False</Private>` on the SDK reference is intentional -- the host
process supplies the DLL at runtime.

## Deploy

Build first, then deploy:

```powershell
.\deploy.ps1                         # Debug -> Dev (default)
.\deploy.ps1 -Config Release         # Release -> Prod
.\deploy.ps1 -Config Debug -Target Prod  # Debug -> Prod (warns, 5s delay)
```

Default mapping: `Debug` -> `Dev` (`C:\QuantowerDev`), `Release` -> `Prod`
(`C:\Quantower`). Destination:
`<QuantowerRoot>\Settings\Scripts\Strategies\PythonBridgeQuantower`.

## Architecture Notes

Architecture is documented in `ARCHITECTURE.md`. If the file does not
exist, create it. It should cover project layout, data flow, wiring
between components, settings design, and the decisions behind each --
including alternatives that were considered and why they were rejected.

When a change affects the wiring between components, adds or removes a
project, or revisits a design decision, update `ARCHITECTURE.md` in the
same commit. Keep the file accurate -- it is the canonical reference for
why things are the way they are, not just what they are.

## Environment & Tech Stack

- .NET 8.0 (Quantower compatibility)
- x64 (required for Quantower)
- Windows 11 ARM running x64 via Prism/emulation
- TradingPlatform.BusinessLayer (Quantower API)
- Python side: `rich` for TUI, stdlib `socket` and `json`

## Reference Source

The sibling repo `..\QuantowerRef` holds the Quantower API reference;
consult when API behavior is unclear from public docs.
`..\auto-size-strategy` is a POCO-factored Strategy reference.

## Coding Standards

- Use C# 14 features compatible with .NET 8.0 (primary constructors,
  collection expressions, `field` keyword).
- PascalCase for methods and properties; prefix private fields with `_`
  or qualify with `this.`.
- Clean up event handlers in `OnStop()`; use `Log()` for diagnostics.
- Use regular comments, not XML doc comments. Comment only where it adds
  context.
- Python side: no logging/print for debugging -- rely on a debugger with
  breakpoints. TUI rendering and `msgs/sec` header are deliberate program
  output, not debug output.

## Git Guidelines

- Style: intent-first, imperative mood. No prefixes like `fix:` or `feat:`.
- Subject: a single strong sentence starting with a verb. Aim for 50 chars,
  absolute max 72.
- Body: 1-5 bullets explaining the why and how.
- Example: `Widen base SL to reduce stop-outs during replay testing`
- Do not include `Co-Authored-By: Claude` in commit messages.
- Always preview the commit message before final execution.

## Text & Encoding Rules

- Strict ASCII only in code, comments, and commit messages.
- No emojis, smart quotes, em/en dashes, or unicode arrows.
- Substitutes: standard hyphen `-`, double hyphen `--`, ASCII arrows
  `->` / `=>`.
- Apply this rule to AGENTS.md itself.

## Testing & E2E

No test project in V0. When applicable:

- Prefer xUnit `[Theory]` + `[InlineData]` only when cases share identical
  execution logic and differ only in input/output values.
- Combine tests only when the underlying business requirement being validated
  is identical. Keep distinct behaviors in separate methods even when setup
  overlaps.
- When verifying E2E logs, derive expected values from first principles --
  never from the code being tested.
