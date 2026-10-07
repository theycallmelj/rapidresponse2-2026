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

## Distribution channels

Information is distributed by *matching the channel to the level of knowledge the decision needs*:

- **Wireless Emergency Alert (all phones), arena PA, and jumbotron** are the public broadcasts that coordinate the city's plan — everyone receives them and sees everyone receive them, creating the common knowledge a corridor or extra-train plan needs to succeed.
- **Notify NYC alerts** deliver official closure information at street level for the shared map.
- **Geotagged social posts and 311/navigation-app reports** feed the map from the crowd, but are *not* relied on for coordination — they only reach secondary knowledge.
- **In-app pings** are the one private channel that works, breaking the volunteer's dilemma by asking the nearest witness to confirm a closure.
- **LinkNYC** - people have the option to use these convenient kiosks to get up-to-date information on closures and recommended routes.

The program of channels forms the public map everyone routes on; the broadcast channels form the common-knowledge plan.

## Does each fan get a route home?

**Yes, per-destination route guidance.** The equilibrium computation on the shared map produces, for every arena exit and transit hub, the recommended route, and the prototype already prints these off: e.g. "Port Authority via 8th Ave & W 42nd," "Herald Sq / PATH via 6th Ave & W 34th." Because this routing is density- and closure-aware, the recommended routes steer fans around barricades and away from crush-level densities, not just to the nearest station.

Fans receive their route through the same coordinated broadcast (the alert links each user to their recommended path for their home destination) plus the routing app or map site showing the shared plan, so everyone is on the same expectation — the condition the paper shows makes the equilibrium both unique and within 4/3 of optimal.

## Contents

- `knicks_chaos_proof.tex` / `.pdf` — the paper
- `knicks_router.py` — density- and closure-aware routing prototype