# Knicks Win Chaos

**Challenge 2 submission** — *Common Knowledge, Coordination, and Equilibrium Routing after a Championship at Madison Square Garden*

## The problem

When the Knicks win, tens of thousands of fans pour out of Madison Square Garden into streets that close unpredictably. Getting everyone home is a problem of *information* and *coordination*: it matters not only what each person knows, but what they know that others know. This repo asks whether official alerts, social media updates, and public reports — the city's three natural information channels — can map street closures and plan alternate routes home.

## Key findings (`knicks_chaos_proof.tex`)

The paper models post-game egress as a Bayesian congestion game on a street graph, with closures as a random state and the three channels as signals. Main results:

1. **Log-odds fusion.** The three channels fuse into a single closure map by adding log-odds; each channel casts a weighted vote.
2. **Selfish routing is near-optimal.** Equilibrium routing on a *shared* map is unique and costs at most 4/3 of a perfectly coordinated evacuation; map error decays exponentially in report volume.
3. **Coordination needs common knowledge.** A coordinated plan (a marshalled corridor plus extra trains) works in equilibrium *iff* it is approximately common knowledge — only public broadcasts create this; social media reaches at best secondary knowledge.
4. **Reporting is a volunteer's dilemma.** Bigger crowds report *less* unless the app breaks the symmetry: pinging individual witnesses or paying for reports overcomes the bystander effect.

The accompanying prototype `knicks_router.py` implements the model on a Midtown grid: it fuses simulated alerts/posts/reports, routes fans with density-aware crowd costs, and detects all closures while cutting crush-risk exposures by half versus naive routing.

## Application: what this empowers city officials to do

- **Map closures live** by fusing Notify NYC alerts, geotagged social posts, and 311/navigation-app reports into one public map, with provable accuracy for sufficient report volume.
- **Get fans home safely** by publishing that shared map — selfish routing on it is within 4/3 of optimal and density-aware costs reduce crowd-crush risk.
- **Coordinate the plan** by *broadcasting* corridor and extra-train plans (Wireless Emergency Alert, arena PA, jumbotron), the only channel that creates the common knowledge the plan needs.
- **Sustain the map** by reporting that doesn't fail: privately ping the nearest witness or reward reports.

## Contents

- `knicks_chaos_proof.tex` / `.pdf` — the paper
- `knicks_router.py` — density- and closure-aware routing prototype