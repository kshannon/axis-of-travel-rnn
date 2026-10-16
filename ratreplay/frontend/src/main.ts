import Alpine from "alpinejs";
import { PAGES } from "./pages";
import { registerShell } from "./state/shell";
import { shellHtml } from "./ui/shell";
import { initTheme } from "./ui/theme";
import "./styles.css";

initTheme();
document.getElementById("app")!.innerHTML = shellHtml(PAGES);
registerShell(PAGES.map((page) => page.id));
Alpine.start();
