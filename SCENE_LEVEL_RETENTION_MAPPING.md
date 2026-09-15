# Scene-Level Retention Mapping

New Analytics tab: **Retention Mapping**

## Supported input
A true audience-retention curve containing:
- retention percentage, plus
- video time/timestamp OR video position percentage

The importer explicitly rejects a normal Content/Performance file that only contains
`Average percentage viewed (%)`.

## Mapping
Retention points are mapped against the permanent:
- `actual_timeline` scenes (`S###`), or
- `transcript_reconstructed` segments (`TS####`)

The UI shows:
- retention at scene start
- retention at scene end
- average scene retention
- retention delta across the scene
- DROP / SPIKE / WEAK HOLD / STABLE signal
- script/transcript text
- visual mode / asset type / overlay type when the Actual Timeline snapshot contains them
- priority drop scenes for investigation

Retention curves replace the prior curve for the selected video to avoid duplicate
points from repeat imports. Existing project/timeline/transcript/performance data is preserved.

The system does not claim causation from retention alone; it identifies investigation
targets and shows the content/visual context present at those timestamps.
