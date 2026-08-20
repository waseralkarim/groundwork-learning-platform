import type { Root } from "mdast";
import { visit } from "unist-util-visit";

/**
 * Turns remark-directive nodes into plain elements carrying a `data-directive`
 * attribute, so the renderer can dispatch on the directive name.
 *
 * The vocabulary is closed and mirrors ALLOWED_DIRECTIVES in the API's content
 * linter. Adding one is deliberately a two-sided change: the linter has to
 * accept it and this renderer has to draw it, which stops the vocabulary from
 * quietly sprawling.
 */
export function remarkDirectiveToElements() {
  return (tree: Root) => {
    visit(tree, (node) => {
      if (
        node.type === "containerDirective" ||
        node.type === "leafDirective" ||
        node.type === "textDirective"
      ) {
        // biome-ignore lint/suspicious/noExplicitAny: mdast directive nodes are untyped here
        const anyNode = node as any;
        if (!anyNode.data) {
          anyNode.data = {};
        }
        const data = anyNode.data;
        data.hName = "div";
        data.hProperties = {
          ...anyNode.attributes,
          "data-directive": anyNode.name,
        };
      }
    });
  };
}
