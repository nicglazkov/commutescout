// Where the phone apps are installed from. One place for every page
// that links to them: the header, the homepage band and /app.

/** The public TestFlight group; anyone with the link can install the beta. */
export const TESTFLIGHT_PUBLIC = "https://testflight.apple.com/join/1CbutYdy";

/**
 * True while no build has cleared Apple's beta review: until one does,
 * the public link tells new testers the beta is not accepting anyone.
 * Pages say so next to the link instead of sending people into that.
 */
export const TESTFLIGHT_IN_REVIEW = true;
export const TESTFLIGHT_IN_REVIEW_NOTE =
  "The iPhone beta is waiting on Apple's review. Until it clears, the link says the beta is not accepting testers. Android installs today.";

/** The newest Android APK, attached to the newest release. */
export const ANDROID_RELEASES =
  "https://github.com/nicglazkov/commutescout-app/releases/latest";

export const APP_REPO = "https://github.com/nicglazkov/commutescout-app";
