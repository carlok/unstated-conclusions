/-
Reading the root of a proof term.

Included textually into a generated file rather than built as a module: this
project owns no Lean package and may not create files inside either
installation. It therefore imports `Lean` and nothing else, and must compile
unchanged under both v4.33.1 and v4.34.0-rc1 -- so it stays on the stable
`Lean.Meta` surface and uses nothing from Mathlib.

Two phases, deliberately split:

  roots   -- head constant at the root of each proof, after wrapper stripping.
             One pass, no pretty-printing, no type inference. The cheap detector.
  detail  -- for one declaration and one explicit argument of its root: the
             stronger statement (the argument's inferred type, with the
             theorem's binders re-abstracted), and the verification, which is
             `addDecl` of that statement proved by that subterm.

The table lives in Python, not here. This file reports what it sees -- a head
constant and, on request, argument types -- and never decides what counts as a
weakening. One source of truth, and no generated Lean.
-/
import Lean
open Lean Meta

namespace Unstated

def isTheorem (ci : ConstantInfo) : Bool :=
  match ci with
  | .thmInfo _ => true
  | _ => false

/-- The proof term of a theorem, or the body of a definition.

NOT `ConstantInfo.value?`, which returns `none` for a `thmInfo` -- a theorem's
proof is reached by matching the constructor. A traversal that trusts `value?`
reports every theorem in the library as having no value, which is
indistinguishable from a library containing no proofs. Both print zero.
ENGINEERING.md 2. -/
def proofOf (ci : ConstantInfo) : Option Expr :=
  match ci with
  | .thmInfo v  => some v.value
  | .defnInfo v => some v.value
  | _           => none

/-- Application positions of the explicit binders of a `∀`-type, in order.

The table names an argument by its index among the explicit ones, because a raw
application position moves with implicit insertion and is not reviewable. This
is what translates the one coordinate into the other. Structural on purpose:
the raw shape is what decides which positions are explicit. -/
partial def explicitPositionsFrom (e : Expr) (i : Nat) (acc : List Nat) : List Nat :=
  match e with
  | .forallE _ _ b bi =>
    explicitPositionsFrom b (i + 1) (if bi.isExplicit then i :: acc else acc)
  | _ => acc.reverse

def explicitPositions (type : Expr) : List Nat := explicitPositionsFrom type 0 []

/-- Wrappers elaboration inserts around a proof. Stripping one is not a
finding -- that is what the `stripped_only` verdict is for -- and the layer
count is reported so the distinction is made downstream rather than guessed.
For each of these the payload is the last argument. -/
def wrappers : List Name :=
  [``id, ``cast, ``Eq.mpr, ``Eq.mp, ``Eq.ndrec, ``Eq.rec, ``of_eq_true]

/-- `Foo.bar._proof_3`, `Foo._auxLemma.7`: auxiliaries elaboration lifts out of
a proof. Descending through them is not a finding either. -/
def isAux (n : Name) : Bool :=
  match n with
  | .str _ s => "_proof_".isPrefixOf s || "_auxLemma".isPrefixOf s
  | _ => false

/-- Peel elaboration wrappers off the root, counting layers.

`whnfCore` and never `whnf`: it beta-reduces, zeta-reduces and projects, but it
does not unfold definitions. That distinction is the whole point. A proof whose
root becomes `le_of_lt` only after unfolding a user definition is a different,
weaker claim -- the definition may be the interesting content -- so this stops
at the definition rather than reporting through it. -/
partial def peel (e : Expr) (layers : Nat) (fuel : Nat) : MetaM (Nat × Expr) := do
  if fuel == 0 then return (layers, e)
  let e ← whnfCore e
  match e.getAppFn with
  | .const n _ =>
    let args := e.getAppArgs
    if wrappers.contains n && args.size > 0 then
      peel (args[args.size - 1]!) (layers + 1) (fuel - 1)
    else if isAux n then
      match (← getEnv).find? n with
      | some ci =>
        match proofOf ci with
        | some v => peel (mkAppN v args) (layers + 1) (fuel - 1)
        | none   => return (layers, e)
      | none => return (layers, e)
    else
      return (layers, e)
  | _ => return (layers, e)

def obj (fields : List (String × Json)) : Json := Json.mkObj fields

def moduleOf (env : Environment) (n : Name) : Json :=
  match env.getModuleFor? n with
  | some m => Json.str (toString m)
  | none   => Json.null

/-- Every constant a term mentions.

`Expr.getUsedConstants`, not a hand-rolled walk. A proof term is a DAG with
heavy sharing, and a naive structural recursion visits shared subterms once per
path into them -- which is fine on small proofs and catastrophic on large ones.
The hand-rolled version finished `Mathlib.Order` (17,632 theorems) in about
forty seconds and did not finish the library in two and a half hours, twice.
Lean ships the function that does this properly because its own compiler needs
it. ENGINEERING.md 21. -/
def constsIn (e : Expr) (acc : NameSet) : NameSet :=
  e.getUsedConstants.foldl (fun s n => s.insert n) acc

/-- Does a term rest on `sorryAx`?

The sibling's rule is that success comes from `#print axioms` and never from the
absence of an error. This project relaxed a related rule -- a compile shot is
accepted on positive evidence rather than on silence -- and that relaxation
opened a door the sibling had closed: Lean inserts `sorryAx` when a tactic
fails, so a declaration whose proof did not work is still *added*, and
`addDecl` on a subterm of it still succeeds. A row could have been reported as
`strengthens` on a proof that proves nothing.

One row in 645 does this: `MulChar.restrictHom_surjective`, which is also the
single row the sibling itself ships as unreproduced. ENGINEERING.md 12. -/
def hasSorry (e : Expr) : Bool :=
  (constsIn e NameSet.empty).contains ``sorryAx

/-- Phase A. The root head of one declaration's proof, and nothing expensive. -/
def rootOf (declName : Name) : MetaM Json := do
  let env ← getEnv
  match env.find? declName with
  | none =>
    return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                ("why", Json.str "not found")]
  | some ci =>
    if !isTheorem ci then
      return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                  ("why", Json.str "not a theorem")]
    else match proofOf ci with
    | none =>
      return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                  ("why", Json.str "no value")]
    | some val =>
      try
        lambdaTelescope val fun _ body => do
          let (layers, root) ← peel body 0 200
          let common : List (String × Json) :=
            [("decl", Json.str (toString declName)), ("module", moduleOf env declName),
             ("ok", Json.bool true), ("layers", Json.num layers)]
          match root.getAppFn with
          | .const head _ =>
            return obj (common ++ [("root", Json.str (toString head)),
                                   ("root_args", Json.num root.getAppArgs.size),
                                   ("has_sorry", Json.bool (hasSorry body))])
          | .fvar _ =>
            return obj (common ++ [("root", Json.null), ("root_kind", Json.str "fvar")])
          | .lam _ _ _ _ =>
            return obj (common ++ [("root", Json.null), ("root_kind", Json.str "lam")])
          | _ =>
            return obj (common ++ [("root", Json.null), ("root_kind", Json.str "other")])
      catch e =>
        return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                    ("why", Json.str (← e.toMessageData.toString))]

/-- The declarations a module actually contains.

Reading them from the module's own data, not by scanning the environment and
asking `getModuleFor?` of every constant. The scanning version worked and was
unusable: a quarter of a million constants per call, fifty calls to render one
gate document, and the run hit a forty-minute timeout. ENGINEERING.md 4.

`moduleNames` and `moduleData` are both on the header and are index-aligned,
which is the one thing this needs and the one thing that is stable across the
two toolchains. -/
def moduleConsts (env : Environment) (m : Name) : Array Name :=
  match env.header.moduleNames.findIdx? (· == m) with
  | some i =>
    match env.header.moduleData[i]? with
    | some d => d.constNames
    | none   => #[]
  | none => #[]

/-- Library declarations whose type is definitionally the stronger statement,
searched in one module.

The duplicate check's cheapest and strongest leg, and it runs *inside* the
process that computed the stronger statement. Running it as a second pass would
mean a second Mathlib import per row -- eighty-five seconds each, doubling a
sixteen-hour sweep to buy nothing.

One module, because that is where the sibling lemma lives when it exists:
BRIEF.md's own failing condition for the gate is "`le_of_lt` closing a `calc`
block with the `_lt` sibling on the next line of the file".

Level parameters are instantiated to fresh metavariables before comparing.
Comparing two types that still quantify over their own universe names finds
nothing and reports every row as unique, which is the flattering answer and
therefore the one to distrust. -/
def defeqSiblings (strongType : Expr) (inModule : Name) (skip : Name)
    (limit : Nat) : MetaM (List Name) := do
  let env ← getEnv
  let mut found : List Name := []
  for n in moduleConsts env inModule do
    if found.length ≥ limit then
      break
    if n == skip || n.isInternal then
      continue
    match env.find? n with
    | none => continue
    | some ci =>
      if !isTheorem ci then
        continue
      let t ←
        if ci.levelParams.isEmpty then pure ci.type
        else do
          let ls ← ci.levelParams.mapM fun _ => mkFreshLevelMVar
          pure (ci.type.instantiateLevelParams ci.levelParams ls)
      if ← withNewMCtxDepth (isDefEq t strongType) then
        found := n :: found
  return found

/-- The head constant of a type's conclusion, ignoring its binders.

A prefilter for the library-wide duplicate search. Comparing every declaration's
type by `isDefEq` is a quarter of a million kernel questions per row; comparing
head symbols first cuts that to the few hundred that could possibly match, and
costs a structural walk. -/
partial def conclusionHead : Expr → Option Name
  | .forallE _ _ b _ => conclusionHead b
  | e => match e.getAppFn with
         | .const n _ => some n
         | _ => none

/-- Library-wide duplicate search: is the stronger statement already a theorem?

This replaces the sibling project's `exact?` stage rather than copying it, and
the reason is a round trip. `exact?` needs the statement as source text, so it
needs the pretty-printer to produce something the parser reads back as the same
type -- and a statement that fails to round-trip is indistinguishable, in the
output, from one the library cannot prove. Comparing the `Expr` directly has no
such failure mode.

It answers a narrower question than `exact?` does, and the narrower one is the
right one here: `exact?` asks *can the library prove this*, which for a
strengthened statement is very often yes and says nothing about whether anyone
wrote it down. This asks *has someone already stated it*, which is the
duplicate rate the project reports as a measurement of API discipline. -/
def librarySiblings (strongType : Expr) (skip : Name) (limit : Nat) : MetaM (List Name) := do
  let env ← getEnv
  let head := conclusionHead strongType
  let mut found : List Name := []
  for (n, ci) in env.constants.toList do
    if found.length ≥ limit then
      break
    if n == skip || n.isInternal || !isTheorem ci then
      continue
    if conclusionHead ci.type != head then
      continue
    let t ←
      if ci.levelParams.isEmpty then pure ci.type
      else do
        let ls ← ci.levelParams.mapM fun _ => mkFreshLevelMVar
        pure (ci.type.instantiateLevelParams ci.levelParams ls)
    if ← withNewMCtxDepth (isDefEq t strongType) then
      found := n :: found
  return found

/-- Phase B. The stronger statement, and its verification.

`which` is an index among the root constant's explicit binders -- the table's
own coordinate. The stronger statement is that argument's inferred type with
the theorem's binders re-abstracted; the proof is the argument itself.

Verification is `addDecl`, not recompilation from source. The subterm is part of
a term the kernel already accepted, so the kernel accepting it again under the
re-abstracted type is the check -- the same test as a recompile, without the
elaborator. What recompilation from source additionally establishes is that the
*shipped text* means this, which is why it still runs on the rows that ship.

Three things are checked rather than assumed, because BRIEF.md says to check
them: that no metavariable survives into either the type or the value; that the
universe levels are the declaration's own (the subterm lives inside its proof
and is parametric in exactly the same levels, so they are taken from the
declaration and never guessed); and whether the "stronger" type is merely defeq
to the stated one, which is not a finding but an elaboration artefact. -/
def detailOf (declName : Name) (which : Nat) (emit : Name)
    (inModule : Name := Name.anonymous) (wide : Bool := false) : MetaM Json := do
  let env ← getEnv
  match env.find? declName with
  | none =>
    return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                ("why", Json.str "not found")]
  | some ci =>
    match proofOf ci with
    | none =>
      return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                  ("why", Json.str "no value")]
    | some val =>
      try
        lambdaTelescope val fun xs body => do
          let (layers, root) ← peel body 0 200
          -- Does the stronger statement actually imply the stated one?
          --
          -- The table's guarantee runs: the selected argument's type implies the
          -- root application's type. That closes the chain only if the root's
          -- type is still the theorem's conclusion. Peeling a wrapper changes
          -- the type -- `Eq.mpr h x` and `x` have different types by
          -- construction -- so when layers > 0 the chain can be broken and the
          -- "stronger" statement can be true and unrelated.
          --
          -- The kernel accepting it says nothing here: `addDecl` checks the
          -- statement is PROVED, not that it implies anything. Two rows in the
          -- first fifty were exactly this. ENGINEERING.md 6.
          let conclusion ← inferType body
          let rootType ← inferType root
          let preserved ← isDefEq rootType conclusion
          match root.getAppFn with
          | .const head _ =>
            match env.find? head with
            | none =>
              return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                          ("why", Json.str "root constant vanished")]
            | some hci =>
              let args := root.getAppArgs
              let positions := explicitPositions hci.type
              match positions[which]? with
              | none =>
                return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                            ("root", Json.str (toString head)),
                            ("why", Json.str s!"root has {positions.length} explicit binders, wanted index {which}")]
              | some pos =>
                if pos ≥ args.size then
                  return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                              ("root", Json.str (toString head)),
                              ("why", Json.str s!"root applied to {args.size} arguments, wanted position {pos}")]
                else
                  let sub := args[pos]!
                  let subType ← instantiateMVars (← inferType sub)
                  let sub ← instantiateMVars sub
                  let strongType ← mkForallFVars xs subType
                  let strongValue ← mkLambdaFVars xs sub
                  let stated := ci.type
                  let same ← isDefEq strongType stated
                  let siblingModule :=
                    if inModule == Name.anonymous then
                      (env.getModuleFor? declName).getD Name.anonymous
                    else inModule
                  let sibs ←
                    if wide then librarySiblings strongType declName 5
                    else if siblingModule == Name.anonymous then pure []
                    else defeqSiblings strongType siblingModule declName 5
                  let common : List (String × Json) :=
                    [("decl", Json.str (toString declName)), ("ok", Json.bool true),
                     ("siblings", Json.arr (sibs.map (fun n => Json.str (toString n))).toArray),
                     ("sibling_module", Json.str (toString siblingModule)),
                     ("sibling_scope", Json.str (if wide then "library" else "module")),
                     ("layers", Json.num layers), ("root", Json.str (toString head)),
                     ("explicit_index", Json.num which), ("position", Json.num pos),
                     ("stronger", Json.str (toString (← ppExpr strongType))),
                     ("stated", Json.str (toString (← ppExpr stated))),
                     ("defeq_to_stated", Json.bool same),
                     ("peel_preserved_type", Json.bool preserved),
                     ("has_sorry", Json.bool (hasSorry strongValue || hasSorry body)),
                     ("levels", Json.num ci.levelParams.length)]
                  if strongType.hasMVar || strongValue.hasMVar then
                    return obj (common ++ [("verify", Json.str "metavariables survived")])
                  else
                    -- A `Nonempty.intro` or `Exists.intro` whose selected
                    -- argument is the WITNESS, not a proof, gives a strengthened
                    -- "statement" that is a Type rather than a Prop. The kernel
                    -- rejects it as a theorem, correctly, and that rejection
                    -- reads as a verification failure when it is nothing of the
                    -- sort: it is stage 2's material, an object the library
                    -- never named. Declared as a `def`. ENGINEERING.md 7.
                    let prop ← isProp strongType
                    let decl :=
                      if prop then
                        Declaration.thmDecl
                          { name := emit, levelParams := ci.levelParams,
                            type := strongType, value := strongValue }
                      else
                        Declaration.defnDecl
                          { name := emit, levelParams := ci.levelParams,
                            type := strongType, value := strongValue,
                            hints := ReducibilityHints.abbrev,
                            safety := DefinitionSafety.safe }
                    let verdict ←
                      try
                        addDecl decl
                        pure (if prop then "added" else "added as a definition")
                      catch e =>
                        pure s!"addDecl failed: {← e.toMessageData.toString}"
                    return obj (common ++ [("verify", Json.str verdict),
                                           ("is_prop", Json.bool prop)])
          | _ =>
            return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                        ("why", Json.str "root is not a constant")]
      catch e =>
        return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                    ("why", Json.str (← e.toMessageData.toString))]

/-- Constants that pull a value out of a proof that one exists.

`Classical.choice` and the `Classical.*` family are the obvious ones. The rest
are not, and leaving them out produced a false zero on the category `BRIEF.md`
predicts should dominate: **`Nonempty.some` is the idiomatic way to do this in
Mathlib**, and it is `Classical.choice` underneath. So is `Exists.choose`, so is
`Trunc.out`. A witness reading `MulChar.mulEquivToUnitHom.trans ⋯.some` came back
`computable`-adjacent while resting on choice. ENGINEERING.md 14.

The list is hand-written for the same reason `weakenings.json` is: a missing
entry reports the flattering answer and nothing catches it. -/
def choiceConstants : List Name :=
  [``Classical.choice, ``Classical.choose, ``Classical.choose_spec,
   ``Classical.indefiniteDescription, ``Classical.byContradiction, ``Classical.em,
   ``Classical.arbitrary, ``Nonempty.some, ``Exists.choose, ``Exists.choose_spec,
   ``Trunc.out, ``Quot.out, ``Classical.dec, ``Classical.propDecidable]

/-- Stage 2. Classify the object a statement quantifies away.

`BRIEF.md` asks for the computable fraction to be measured before anything is
claimed, because most existentials in Mathlib are expected to go through
`Classical.choose` -- in which case the witness is not a new object and stage 2
is a footnote. That expectation is a prediction, and this is what tests it.

The categories are the brief's:

  computable                  -- a closed term in the theorem's parameters
  noncomputable_choice        -- routed through `Classical.choose` and friends
  noncomputable_other         -- some other noncomputable constant
  depends_on_hypothesis_proof -- the term mentions a proof of a hypothesis.
                                 Legitimate in dependent type theory, and
                                 flagged rather than counted as either.
  not_closed                  -- loose bound variables survived. A tool failure,
                                 counted apart so it cannot inflate the rest.

`fvars` are the theorem's own binders, which the witness is allowed to mention:
being a function of the parameters is what makes it an object worth naming. A
binder whose type is a Prop is a different matter -- a witness computed from a
proof is not a construction anyone can run. -/
def classifyWitness (witness : Expr) (binders : Array Expr) : MetaM Json := do
  let consts := (constsIn witness NameSet.empty).toList
  let choice := consts.filter (fun n => choiceConstants.contains n)
  let mut nonComp : List Name := []
  for n in consts do
    if (← getEnv).find? n |>.isSome then
      if isNoncomputable (← getEnv) n then
        nonComp := n :: nonComp
  -- A binder the witness mentions, and whether it is a hypothesis or an
  -- instance. Both are proofs when their type is a Prop, and the brief asks for
  -- the hypothesis case to be flagged -- but a Prop-valued typeclass is not a
  -- hypothesis, and counting the two together overstates how often a witness
  -- rests on an assumption someone made. ENGINEERING.md 15.
  let mut proofDeps : List String := []
  let mut instDeps : List String := []
  for b in binders do
    if witness.containsFVar b.fvarId! then
      if ← Meta.isProof b then
        let decl ← b.fvarId!.getDecl
        let name := toString decl.userName
        if decl.binderInfo == BinderInfo.instImplicit then
          instDeps := name :: instDeps
        else
          proofDeps := name :: proofDeps
  let kind :=
    if witness.hasLooseBVars then "not_closed"
    else if !choice.isEmpty then "noncomputable_choice"
    else if !proofDeps.isEmpty then "depends_on_hypothesis_proof"
    else if !nonComp.isEmpty then "noncomputable_other"
    else "computable"
  return obj [("kind", Json.str kind),
              ("choice", Json.arr (choice.map (fun n => Json.str (toString n))).toArray),
              ("noncomputable",
               Json.arr (nonComp.map (fun n => Json.str (toString n))).toArray),
              ("proof_deps", Json.arr (proofDeps.map Json.str).toArray),
              ("instance_deps", Json.arr (instDeps.map Json.str).toArray),
              ("constants", Json.num consts.length)]

/-- Stage 2 on one declaration: the witness, its type, and its classification.

`which` is the table's `witness_arg` -- the argument holding the object, not the
one holding the proof about it. -/
def witnessOf (declName : Name) (which : Nat) : MetaM Json := do
  let env ← getEnv
  match env.find? declName with
  | none => return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                        ("why", Json.str "not found")]
  | some ci =>
    match proofOf ci with
    | none => return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                          ("why", Json.str "no value")]
    | some val =>
      try
        lambdaTelescope val fun xs body => do
          let (layers, root) ← peel body 0 200
          match root.getAppFn with
          | .const head _ =>
            match env.find? head with
            | none => return obj [("decl", Json.str (toString declName)),
                                  ("ok", Json.bool false),
                                  ("why", Json.str "root constant vanished")]
            | some hci =>
              let args := root.getAppArgs
              match (explicitPositions hci.type)[which]? with
              | none => return obj [("decl", Json.str (toString declName)),
                                    ("ok", Json.bool false),
                                    ("why", Json.str "no such explicit argument")]
              | some pos =>
                if pos ≥ args.size then
                  return obj [("decl", Json.str (toString declName)),
                              ("ok", Json.bool false),
                              ("why", Json.str "root under-applied")]
                else
                  let w ← instantiateMVars args[pos]!
                  let wType ← inferType w
                  let classified ← classifyWitness w xs
                  return obj [("decl", Json.str (toString declName)), ("ok", Json.bool true),
                              ("root", Json.str (toString head)), ("layers", Json.num layers),
                              ("witness", Json.str (toString (← ppExpr w))),
                              ("witness_type", Json.str (toString (← ppExpr wType))),
                              ("classification", classified)]
          | _ => return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                             ("why", Json.str "root is not a constant")]
      catch e =>
        return obj [("decl", Json.str (toString declName)), ("ok", Json.bool false),
                    ("why", Json.str (← e.toMessageData.toString))]

/-- How many declarations in the library cite each constant.

Asked for by `unused-assumptions` to settle a question its own proxies cannot:
are the theorems it finds carrying unused hypotheses *classical results* or
*working lemmas written once in service of a proof*? Its three proxies are all
about naming, and naming is a convention rather than a measurement. A citation
count is a fact about the library.

Definitions, because a count means nothing without them:

- A declaration **cites** a constant when the constant appears anywhere in its
  proof term. Statement types reached through the term are included; a lemma
  mentioned only in the statement and never used is rare and is not worth a
  second pass to exclude.
- Counted **once per citing declaration**, not once per occurrence. Ten uses of
  `le_of_lt` in one proof is one citation. Otherwise a long proof outvotes a
  library.
- Only theorems cite. Definitions have bodies rather than proofs, and counting
  them would mix "this lemma is used in arguments" with "this definition is
  built from that one".
- Self-citation is dropped.

Emitting the counts rather than the sets is deliberate: the sets are roughly
fourteen million pairs and the counts are what the question needs. -/
def citationCounts (modulePrefix : String) : MetaM Unit := do
  let env ← getEnv
  let mut counts : Std.HashMap Name Nat := {}
  -- Annotated. Without it `Json.num scanned` below infers `JsonNumber`
  -- and the increment then wants `HAdd JsonNumber Nat`.
  let mut scanned : Nat := 0
  for (name, ci) in env.constants.toList do
    if !isTheorem ci || name.isInternal then
      continue
    match env.getModuleFor? name with
    | none => continue
    | some m =>
      if !modulePrefix.isPrefixOf (toString m) then
        continue
      match proofOf ci with
      | none => continue
      | some val =>
        scanned := scanned + 1
        for c in (constsIn val NameSet.empty).toList do
          if c != name && !c.isInternal then
            counts := counts.insert c ((counts.get? c).getD 0 + 1)
  IO.println (Json.mkObj [("scanned_theorems", Json.num scanned),
                          ("cited_constants", Json.num counts.size)]).compress
  for (name, count) in counts.toList do
    IO.println (Json.mkObj [("decl", Json.str (toString name)),
                            ("cited_by", Json.num count)]).compress

def emitLine (j : Json) : MetaM Unit := IO.println j.compress

def roots (names : List Name) : MetaM Unit :=
  names.forM fun n => do emitLine (← rootOf n)

/-- Phase A over every theorem in the environment whose defining module starts
with `modulePrefix`. One pass -- this is the traversal the cost argument rests
on: reading the root of a proof term is milliseconds per declaration, so the
question is asked of the whole library in one process rather than swept.

The module, not the name: a Mathlib theorem is called `le_of_lt`, not
`Mathlib.le_of_lt`, so filtering on the declaration name would silently select
nothing and the corpus would read as empty. Something that resolved nothing
looks exactly like something that contained nothing. -/
def rootsAll (modulePrefix : String) : MetaM Unit := do
  let env ← getEnv
  for (name, ci) in env.constants.toList do
    if isTheorem ci && !name.isInternal then
      match env.getModuleFor? name with
      | some m => if modulePrefix.isPrefixOf (toString m) then emitLine (← rootOf name)
      | none => pure ()

/-- Does a constant exist, with the explicit arity the table claims?

An entry naming a constant that does not resolve is an error, never a silent
miss: a wrong entry reports "no slack" and nothing catches it. -/
def checkTable (names : List Name) : MetaM Unit :=
  names.forM fun n => do
    let env ← getEnv
    match env.find? n with
    | none => emitLine (obj [("root", Json.str (toString n)), ("found", Json.bool false)])
    | some ci =>
      emitLine (obj [("root", Json.str (toString n)), ("found", Json.bool true),
                     ("explicit_arity", Json.num (explicitPositions ci.type).length)])

end Unstated
