import Alpine from "alpinejs";
import { createPair, errorText, listSets, pairArrays, pairBlock, setGuesses, submitGuess } from "../api/client";
import type { PairArrays, PairHeader, SetRow, Side, Tally } from "../api/types";
import { EnvironmentBackdrop, extentOf } from "../draw/environment";
import { timeLabel } from "../draw/lanes";
import { MapView, THIN_PATH } from "../draw/map";
import { Timeline } from "../draw/timeline";
import { Visit } from "../router";
import { Clock, REAL_TIME, SPEEDS, stepSpeed } from "../session/clock";
import { startPlayback } from "../session/playback";
import { speedTop } from "../session/speed";
import { folderPage } from "../ui/gate";
import { toast } from "../ui/toast";
import type { Page } from "./page";
import { quizRoot } from "./quiz-html";
import {
  ANY_KIND, EMPTY_SCENE, EMPTY_TALLY, guessBlocked, kindChoices, newPairBlocked, revealLine, setChoices, sharedFrames, sideChip, sideIndex, SIDES, speedScene, tallyLine, tallyRows,
} from "./quiz-view";
import type { Choice, Phase, TallyRow } from "./quiz-view";

// The set and the kind chosen, kept while the person visits other pages.
let chosenSet = "";
let chosenKind = ANY_KIND;

interface SideViews {
  map: MapView;
  timeline: Timeline;
}

interface LoadedSide {
  header: PairHeader;
  arrays: PairArrays;
}

function registerQuiz(): void {
  Alpine.data("quizPage", () => {
    // The two sides' arrays and views live in plain objects, only scalars and small lists go to Alpine.
    const visit = new Visit();
    const views = {} as Record<Side, SideViews>;
    let sides: Record<Side, LoadedSide> | null = null;
    let clock: Clock | null = null;
    let pairId = "";
    // Each read is numbered so that only the latest answer lands.
    let latest = 0;
    let stopPlayback = () => {};

    return {
      loading: true,
      error: "",
      rows: [] as SetRow[],
      sets: [] as Choice[],
      setId: chosenSet,
      kind: chosenKind,
      kinds: kindChoices([]) as Choice[],
      phase: "empty" as Phase,
      pairKind: "",
      tallyText: tallyLine(EMPTY_TALLY),
      tallyRows: [] as TallyRow[],
      chips: { left: "", right: "" } as Record<Side, string>,
      verdict: "",
      correct: false,
      playing: false,
      speeds: SPEEDS,
      speedIndex: REAL_TIME,
      time: "",

      get loaded() {
        return this.phase === "open" || this.phase === "answered";
      },
      get newPairBlocked() {
        return newPairBlocked(this.setId, this.phase);
      },
      get guessBlocked() {
        return guessBlocked(this.phase);
      },
      get speedLabel() {
        return `${SPEEDS[this.speedIndex]}x`;
      },

      /** The views of both sides, then the sets, with the latest set chosen unless one was chosen on the last visit. */
      async init() {
        await this.$nextTick();
        if (!visit.shown) return;
        for (const side of SIDES) {
          views[side] = {
            map: new MapView(this.$refs[`${side}Map`]),
            timeline: new Timeline(this.$refs[`${side}Lanes`], { seek: (index) => this.seek(index), view: () => {} }),
          };
          views[side].timeline.load(EMPTY_SCENE);
        }
        stopPlayback = startPlayback(this);
        this.$watch("$store.shell.dark", () => {
          for (const side of SIDES) {
            views[side].map.refresh();
            views[side].timeline.refresh();
          }
        });
        this.$watch("kind", (kind: string) => (chosenKind = kind));
        try {
          this.rows = await listSets();
          this.sets = setChoices(this.rows);
          if (!this.sets.some((choice) => choice.value === this.setId)) this.setId = this.sets[0]?.value ?? "";
          await this.chooseSet();
        } catch (error) {
          this.error = errorText(error);
        }
        this.loading = false;
      },

      destroy() {
        visit.hide();
        stopPlayback();
        for (const side of SIDES) {
          views[side]?.map.destroy();
          views[side]?.timeline.destroy();
        }
      },

      /** The set changed: its kinds, no pair, and its tally. */
      async chooseSet() {
        chosenSet = this.setId;
        this.kinds = kindChoices(this.rows.find((row) => row.set_id === this.setId)?.kinds ?? []);
        if (!this.kinds.some((choice) => choice.value === this.kind)) this.kind = ANY_KIND;
        this.clear();
        if (!this.setId) {
          this.showTally(EMPTY_TALLY);
          return;
        }
        const mine = ++latest;
        const { tally } = await setGuesses(this.setId);
        if (mine !== latest || !visit.shown) return;
        this.showTally(tally);
      },

      async changeSet() {
        try {
          await this.chooseSet();
        } catch (error) {
          visit.say(() => toast.error(errorText(error)));
        }
      },

      showTally(tally: Tally) {
        this.tallyText = tallyLine(tally);
        this.tallyRows = tallyRows(tally);
      },

      /** No pair: the sides blank, nothing to answer. */
      clear() {
        latest++;
        sides = null;
        clock = null;
        pairId = "";
        this.phase = "empty";
        this.pairKind = "";
        this.chips = { left: "", right: "" };
        this.verdict = "";
        this.playing = false;
        this.time = "";
        for (const side of SIDES) {
          views[side].map.clear();
          views[side].timeline.load(EMPTY_SCENE);
        }
      },

      /** Open a pair of the set and draw both sides on one colour scale, so the scale tells nothing. */
      async newPair() {
        this.clear();
        const mine = latest;
        this.phase = "loading";
        try {
          const pair = await createPair(this.setId, this.kind || null);
          const [left, right] = await Promise.all(SIDES.map(async (side): Promise<LoadedSide> => {
            const [header, arrays] = await Promise.all([pairBlock(pair.pair_id, side), pairArrays(pair.pair_id, side)]);
            return { header, arrays };
          }));
          if (mine !== latest || !visit.shown) return;
          sides = { left, right };
          pairId = pair.pair_id;
          this.pairKind = pair.kind;
          const top = Math.max(speedTop(left.arrays.speed), speedTop(right.arrays.speed));
          clock = new Clock(sharedFrames([left.header, right.header], left.header.rate_hz), left.header.rate_hz);
          clock.setSpeed(SPEEDS[this.speedIndex], performance.now());
          for (const side of SIDES) {
            const { header, arrays } = sides[side];
            views[side].timeline.load(speedScene(header, arrays, top));
            views[side].map.load({ ...arrays, rateHz: header.rate_hz }, new EnvironmentBackdrop(header.geometry, extentOf(header.geometry, arrays.x, arrays.y)), top);
            views[side].map.setStretches([{ first: 1, last: header.row.n_frames, ...THIN_PATH }]);
          }
          this.phase = "open";
          this.show();
        } catch (error) {
          if (mine !== latest) return;
          this.phase = "empty";
          visit.say(() => toast.error(errorText(error)));
        }
      },

      /** Say which side is real: the server reveals the pair, records the guess and gives the set's tally. */
      async guess(side: Side) {
        if (this.guessBlocked) return;
        const mine = latest;
        this.phase = "answered";
        try {
          const reveal = await submitGuess(this.setId, pairId, side);
          if (mine !== latest || !visit.shown) return;
          this.chips = { left: sideChip(reveal, "left"), right: sideChip(reveal, "right") };
          this.verdict = revealLine(reveal);
          this.correct = reveal.correct;
          this.showTally(reveal.tally);
        } catch (error) {
          if (mine !== latest) return;
          this.phase = "open";
          visit.say(() => toast.error(errorText(error)));
        }
      },

      /** Redraw what follows the shared clock: each side's cursor and map at its own frame, and the time as the timelines label it. */
      show() {
        if (!sides || !clock) return;
        for (const side of SIDES) {
          const index = sideIndex(clock.index, clock.rateHz, sides[side].header);
          views[side].timeline.setCursor(index);
          views[side].map.draw(index);
        }
        this.time = timeLabel(clock.index / clock.rateHz);
      },
      clock() {
        return clock;
      },
      runStarts() {
        return [];
      },

      togglePlay() {
        clock!.toggle(performance.now());
        this.playing = clock!.playing;
      },
      changeSpeed(direction: -1 | 1) {
        this.speedIndex = stepSpeed(this.speedIndex, direction);
        clock?.setSpeed(SPEEDS[this.speedIndex], performance.now());
      },
      seek(index: number) {
        if (!clock) return;
        clock.seek(index, performance.now());
        this.show();
      },
    };
  });
}

export const quizPage: Page = {
  id: "quiz",
  title: "Real or synthetic",
  html: folderPage("Real or synthetic", quizRoot, "processed", "synthetic", "environments"),
  register: registerQuiz,
};
