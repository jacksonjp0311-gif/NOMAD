# NOMAD Architecture — v0.8 WORLD MODEL

```text
                         GOAL
                          │
                          ▼
                  REPOSITORY SENSORS
          imports · AST · tests · failures · reachability
                          │
                          ▼
                     WORLD MODEL
       failure evidence × repository structure → location belief
                          │
                          ▼
                  TRANSFORMATION SEARCH
             causal skills · RESONANCE · ECHO MAP
                          │
                          ▼
                     TRANSMISSION
                          │
                          ▼
                       WORLD
                          │
                          ▼
                       ECHO
                          │
                          ▼
                      WITNESS
                          │
              factual consequence receipt
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
      durable evidence              contradiction
```

## Authority separation

WORLD MODEL may rank candidate locations. It cannot certify that a location caused the observed failure. Location learning is admitted only from WITNESS-supported repairs.

WITNESS remains independent of search ranking and checks only observable consequences on disjoint evidence.

## World state

For a repository graph `G`, candidate file `f` and current evidence `E_t`, NOMAD constructs

`σ_f = Φ(G, f, E_t)`.

Current observables include graph distance, reachability, degree, AST predicates, available transformation families and failure geometry. Filenames are excluded.

The model learns interactions because development showed that treating structure and failure evidence as independent features lost the information needed for reliable localization.

## Relationship to Bitwork

Bitwork's central pattern remains intact:

- state is compact and explicit;
- transformations are enumerable;
- consequences update evidence;
- contradiction is retained;
- unsupported certainty is avoided;
- expensive search is spent selectively.

WORLD MODEL moves the state boundary outward from one program expression to a graph of interacting software components.
