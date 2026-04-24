export const CONTACT_PATH = "/contact";

export function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function goToContactPage() {
  navigate(CONTACT_PATH);
}
