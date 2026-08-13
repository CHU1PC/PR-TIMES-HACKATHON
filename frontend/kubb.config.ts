import { defineConfig } from "@kubb/core";
import { pluginOas } from "@kubb/plugin-oas";
import { pluginTs } from "@kubb/plugin-ts";
import { pluginZod } from "@kubb/plugin-zod";

export default defineConfig({
  input: { path: "./openapi.json" },
  // clean を切るとモデル改名時に古いファイルが残る
  output: { path: "./src/gen", clean: true },
  // plugin-zod は plugin-ts を前提にする。型は ts, 検証は zod と出所を分ける
  plugins: [pluginOas(), pluginTs(), pluginZod()],
});
