type GoogleCredentialResponse = {
  credential?: string;
};

type GooglePromptNotification = {
  isNotDisplayed?: () => boolean;
  isSkippedMoment?: () => boolean;
  isDismissedMoment?: () => boolean;
  getNotDisplayedReason?: () => string;
  getSkippedReason?: () => string;
  getDismissedReason?: () => string;
};

type GoogleIdentityApi = {
  initialize: (config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    auto_select?: boolean;
    cancel_on_tap_outside?: boolean;
  }) => void;
  prompt: (listener?: (notification: GooglePromptNotification) => void) => void;
  cancel?: () => void;
};

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: GoogleIdentityApi;
      };
    };
  }
}

const GOOGLE_GSI_SCRIPT_URL = "https://accounts.google.com/gsi/client";
let scriptLoadPromise: Promise<void> | null = null;

const loadGoogleIdentityScript = async (): Promise<void> => {
  if (window.google?.accounts?.id) return;
  if (scriptLoadPromise) return scriptLoadPromise;

  scriptLoadPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GOOGLE_GSI_SCRIPT_URL}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Google Identity script failed to load.")), {
        once: true,
      });
      return;
    }

    const script = document.createElement("script");
    script.src = GOOGLE_GSI_SCRIPT_URL;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Google Identity script failed to load."));
    document.head.appendChild(script);
  });

  return scriptLoadPromise;
};

const resolveGoogleApi = (): GoogleIdentityApi => {
  const api = window.google?.accounts?.id;
  if (!api) {
    throw new Error("Google Identity API is unavailable.");
  }
  return api;
};

export const requestGoogleIdToken = async (clientId: string): Promise<string> => {
  const normalizedClientId = clientId.trim();
  if (!normalizedClientId) {
    throw new Error("Google Client ID is not configured.");
  }

  await loadGoogleIdentityScript();
  const googleApi = resolveGoogleApi();

  return new Promise<string>((resolve, reject) => {
    let settled = false;

    const finish = (resolver: () => void) => {
      if (settled) return;
      settled = true;
      resolver();
    };

    const timeoutId = window.setTimeout(() => {
      finish(() => reject(new Error("Google authorization timed out.")));
    }, 60_000);

    const clearTimer = () => window.clearTimeout(timeoutId);

    googleApi.cancel?.();
    googleApi.initialize({
      client_id: normalizedClientId,
      auto_select: false,
      cancel_on_tap_outside: true,
      callback: (response) => {
        const credential = (response.credential || "").trim();
        if (!credential) {
          clearTimer();
          finish(() => reject(new Error("Google credential is missing.")));
          return;
        }
        clearTimer();
        finish(() => resolve(credential));
      },
    });

    googleApi.prompt((notification) => {
      if (settled) return;
      if (notification.isNotDisplayed?.()) {
        clearTimer();
        const reason = notification.getNotDisplayedReason?.() || "unknown";
        finish(() => reject(new Error(`Google prompt is not displayed (${reason}).`)));
        return;
      }
      if (notification.isSkippedMoment?.()) {
        clearTimer();
        const reason = notification.getSkippedReason?.() || "unknown";
        finish(() => reject(new Error(`Google prompt was skipped (${reason}).`)));
        return;
      }
      if (notification.isDismissedMoment?.()) {
        const reason = notification.getDismissedReason?.() || "unknown";
        if (reason !== "credential_returned") {
          clearTimer();
          finish(() => reject(new Error(`Google prompt was dismissed (${reason}).`)));
        }
      }
    });
  });
};

