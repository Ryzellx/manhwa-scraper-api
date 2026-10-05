import { createApp } from "./src/app.js";
const port = process.env.PORT || 8078;
createApp().listen(port, "0.0.0.0", () => console.log(`manhwa-node listening on :${port}`));
