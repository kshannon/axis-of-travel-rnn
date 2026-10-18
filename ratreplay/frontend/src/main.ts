import Alpine from "alpinejs";
import { PAGES } from "./pages";
import { healthStore, registerHealth } from "./state/health";
import { registerSettings } from "./state/settings";
import { registerShell } from "./state/shell";
import { shellHtml } from "./ui/shell";
import { initTheme } from "./ui/theme";
import { registerToasts } from "./ui/toast";
import "./styles.css";

initTheme();
document.getElementById("app")!.innerHTML = shellHtml(PAGES);
registerShell(PAGES.map((page) => page.id));
registerToasts();
registerHealth();
registerSettings();
PAGES.forEach((page) => page.register?.());
Alpine.start();
void healthStore().load();
