# Definizione classica del nodo dell'albero binario
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def binaryTreePaths(root):
    """
    :type root: Optional[TreeNode]
    :rtype: List[str]
    """
    if not root:
        return []

    paths = []

    def dfs(node, current_path):
        if not node:
            return
        
        # Aggiungi il nodo corrente al percorso
        if current_path:
            current_path += "->" + str(node.val)
        else:
            current_path = str(node.val)
        
        # Se il nodo è una foglia, aggiungi il percorso alla lista finale
        if not node.left and not node.right:
            paths.append(current_path)
            return
        
        # Chiamata ricorsiva sui figli
        dfs(node.left, current_path)
        dfs(node.right, current_path)

    dfs(root, "")
    return paths

    # Crea un albero binario di altezza 2
    #       1
    #      / \
    #     2   3
    #    / \
    #   4   5
root = TreeNode(1)
root.left = TreeNode(2)
root.right = TreeNode(3)
root.left.left = TreeNode(4)
root.left.right = TreeNode(5)
# Ottieni tutti i percorsi dalla radice alle foglie
result = binaryTreePaths(root)
print(result)  # Output: ["1->2->4", "1->2->5", "1->3"]