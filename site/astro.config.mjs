// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";

// https://astro.build/config
export default defineConfig({
  site: "https://quartobot.github.io",
  base: "/quartobot",
  integrations: [
    starlight({
      title: "quartobot",
      description: "Citation resolution and manuscript-as-software CI for Quarto.",
      logo: { src: "./src/assets/logo.svg", replacesTitle: false },
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/quartobot/quartobot",
        },
      ],
      editLink: {
        baseUrl: "https://github.com/quartobot/quartobot/edit/main/site/",
      },
      // Sidebar grouped by Diataxis quadrant — Tutorials (learning),
      // How-to guides (doing), Reference (information), Explanation
      // (understanding). Reader intent up front; topic comes second.
      sidebar: [
        { label: "Home", link: "/" },
        {
          label: "Tutorials",
          items: [
            { label: "First manuscript (15 min)", link: "/first-manuscript/" },
            { label: "Getting started", link: "/getting-started/" },
            { label: "MCP + Claude Desktop", link: "/mcp-claude-desktop/" },
            { label: "Shell-tool agent", link: "/shell-tool-agent/" },
          ],
        },
        {
          label: "How-to guides",
          items: [
            { label: "Resolve a single citation", link: "/resolve-single-citation/" },
            { label: "Use a Quarto website", link: "/quarto-websites/" },
            { label: "MCP server", link: "/mcp/" },
            { label: "Migrate from manubot", link: "/migrating-from-manubot/" },
            { label: "Validate a manuscript", link: "/validate-manuscript/" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "Install", link: "/install/" },
            { label: "CLI", link: "/cli/" },
          ],
        },
        {
          label: "Explanation",
          items: [
            { label: "Design", link: "/design/" },
            { label: "Differences from manubot", link: "/differences-from-manubot/" },
          ],
        },
      ],
    }),
  ],
});
