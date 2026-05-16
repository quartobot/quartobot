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
      description: "The manubot manuscript-as-software pattern, on Quarto.",
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
      sidebar: [
        { label: "Home", link: "/" },
        { label: "Getting started", link: "/getting-started/" },
        { label: "Install", link: "/install/" },
        {
          label: "Templates",
          items: [
            { label: "Manuscript", link: "/template/" },
            { label: "Book", link: "/book/" },
          ],
        },
        { label: "CLI", link: "/cli/" },
        { label: "MCP server", link: "/mcp/" },
        {
          label: "From manubot",
          items: [
            { label: "Differences", link: "/differences-from-manubot/" },
            { label: "Migration", link: "/migrating-from-manubot/" },
          ],
        },
        { label: "Design", link: "/design/" },
      ],
    }),
  ],
});
