// Runtime wiring of the shared A0 fixtures for the devkit's OWN lifecycle
// suite. The testkit's fixtures factory takes the consumer's `test` (because
// "@playwright/test" isn't resolvable from the submodule path in consumer
// repos) — here the devkit IS the repo, so we import it directly.
import { test as base } from "@playwright/test";

import { createA0Fixtures } from "../fixtures";

export const test = createA0Fixtures(base);
export { expect } from "@playwright/test";
