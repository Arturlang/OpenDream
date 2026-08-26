using DMCompiler.Compiler.DM.AST;

namespace DMCompiler.DM.Builders;

internal class DMCodeTreeBuilder(DMCompiler compiler) {
    private bool _leftDMStandard;

    private DMCodeTree CodeTree => compiler.DMCodeTree;

    public void BuildCodeTree(DMASTFile astFile) {
        _leftDMStandard = false;

        // Add everything in the AST to the code tree
        compiler.BeginPhase("  walk ast");
        ProcessBlockInner(astFile.BlockInner, DreamPath.Root);

        // Now define everything in the code tree
        compiler.BeginPhase("  define types");
        CodeTree.DefineEverything();
        if (compiler.Settings.PrintCodeTree)
            CodeTree.Print();

        // Create each types' initialization proc (initializes vars that aren't constants)
        compiler.BeginPhase("  init procs");
        foreach (DMObject dmObject in compiler.DMObjectTree.AllObjects)
            dmObject.CreateInitializationProc();

        // Compile every proc
        compiler.BeginPhase("  compile procs");
        foreach (DMProc proc in compiler.DMObjectTree.AllProcs) {
            proc.Compile();
            compiler.CountPhaseItem("  compile procs");
        }

        compiler.EndPhase();
    }

    /// <summary>
    /// Whether this path is the header of a `var` block rather than a type of its own.
    /// </summary>
    private static bool IsDeclarationBlock(DreamPath path) {
        foreach (var element in path.Elements) {
            if (element is "var" or "proc" or "verb")
                return true;
        }

        return false;
    }

    private void ProcessBlockInner(DMASTBlockInner blockInner, DreamPath currentType) {
        foreach (DMASTStatement statement in blockInner.Statements) {
            ProcessStatement(statement, currentType);
        }
    }

    private void ProcessStatement(DMASTStatement statement, DreamPath currentType) {
        if (!_leftDMStandard && !statement.Location.InDMStandard) {
            _leftDMStandard = true;
            CodeTree.FinishDMStandard();
        }

        switch (statement) {
            case DMASTInvalidStatement: // An error should have been emitted by whatever made this
            case DMASTNullStatement:
                break;
            case DMASTObjectDefinition objectDefinition:
                // A block-form declaration - `var` on its own line followed by an indented
                // block - parses as a path with a block after it, exactly like a type does.
                // It is not one: `var` is a reserved word and BYOND declares no such type.
                // Registering it put a phantom /whatever/var into the tree, which typesof()
                // then handed out as though it were real. TGMC's asset subsystem walks
                // typesof(/datum/asset) and tries to instantiate everything it finds, so a
                // single VAR_PRIVATE block was enough to break every spritesheet asset.
                //
                // The inner block is still walked with the full path, because that is what
                // ObjVarDeclInfo strips the `var` off to find the variable's real owner.
                if (!IsDeclarationBlock(objectDefinition.Path))
                    CodeTree.AddType(objectDefinition.Path);

                if (objectDefinition.InnerBlock != null)
                    ProcessBlockInner(objectDefinition.InnerBlock, objectDefinition.Path);
                break;
            case DMASTObjectVarDefinition varDefinition:
                CodeTree.AddType(varDefinition.ObjectPath);
                CodeTree.AddObjectVar(varDefinition.ObjectPath, varDefinition);
                break;
            case DMASTObjectVarOverride varOverride:
                CodeTree.AddType(varOverride.ObjectPath);
                CodeTree.AddObjectVarOverride(varOverride.ObjectPath, varOverride);
                break;
            case DMASTProcDefinition procDefinition:
                var procOwner = currentType.Combine(procDefinition.ObjectPath);

                CodeTree.AddType(procOwner);
                CodeTree.AddProc(procOwner, procDefinition);
                break;
            case DMASTMultipleObjectVarDefinitions multipleVarDefinitions: {
                foreach (DMASTObjectVarDefinition varDefinition in multipleVarDefinitions.VarDefinitions) {
                    CodeTree.AddType(varDefinition.ObjectPath);
                    CodeTree.AddObjectVar(varDefinition.ObjectPath, varDefinition);
                }

                break;
            }
            default:
                compiler.ForcedError(statement.Location, $"Invalid object statement {statement.GetType()}");
                break;
        }
    }
}
