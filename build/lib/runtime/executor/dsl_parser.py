"""DSL Parser - parses tokens into an Agent DSL AST."""

from __future__ import annotations

from runtime.executor.dsl_lexer import Lexer, Token
from runtime.executor.dsl_types import (
    AgentDSL,
    ConditionalBranch,
    DSLArrayLiteral,
    DSLBinaryOp,
    DSLCall,
    DSLCapability,
    DSLCondition,
    DSLConditionalStep,
    DSLExpression,
    DSLFunctionCall,
    DSLGovernance,
    DSLInput,
    DSLLiteral,
    DSLLoop,
    DSLMetadata,
    DSLNode,
    DSLOutput,
    DSLParallel,
    DSLPropertyAccess,
    DSLRetry,
    DSLStep,
    DSLTool,
    DSLTryCatch,
    DSLUnaryOp,
    DSLVariable,
    ParseResult,
    SourceLocation,
)


class DSLParser:
    def __init__(self, filename: str = "<unknown>") -> None:
        self.filename = filename
        self._tokens: list[Token] = []
        self._pos = 0
        self._errors: list[dict] = []

    def parse(self, source: str, filename: str = "") -> ParseResult:
        self.filename = filename or self.filename
        self._errors.clear()
        lexer = Lexer(source, self.filename)
        self._tokens = lexer.tokenize()
        self._pos = 0
        try:
            ast = self._parse_agent()
            return ParseResult(success=len(self._errors) == 0, ast=ast, errors=self._errors)
        except Exception as e:
            self._errors.append({"kind": "syntax", "message": str(e), "loc": self._current().loc})  # type: ignore[attr-defined]
            return ParseResult(success=False, errors=self._errors)

    def parse_tokens(self, tokens: list[Token]) -> ParseResult:
        self._tokens = tokens
        self._pos = 0
        self._errors.clear()
        try:
            ast = self._parse_agent()
            return ParseResult(success=len(self._errors) == 0, ast=ast, errors=self._errors)
        except Exception as e:
            self._errors.append({"kind": "syntax", "message": str(e)})
            return ParseResult(success=False, errors=self._errors)

    @property
    def _current_token(self) -> Token:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else Token(type="EOF")

    def _advance(self) -> Token:
        tok = self._current_token
        self._pos += 1
        return tok

    def _match(self, *types: str) -> bool:
        if self._current_token.type in types:
            self._advance()
            return True
        return False

    def _expect(self, *types: str) -> Token:
        tok = self._current_token
        if tok.type not in types:
            self._error(f"Expected {types}, got '{tok.type}' ('{tok.value}')", tok.loc)
        return self._advance()

    def _create_loc(self, loc: SourceLocation) -> SourceLocation:
        return SourceLocation(file=self.filename, line=loc.line, column=loc.column)

    def _error(self, msg: str, loc: SourceLocation) -> None:
        self._errors.append({"kind": "syntax", "message": msg, "loc": loc})

    def _parse_agent(self) -> AgentDSL:
        self._expect("KEYWORD")  # agent
        name_tok = self._expect("IDENTIFIER", "KEYWORD")
        agent = AgentDSL(name=name_tok.value, loc=self._create_loc(name_tok.loc))
        self._expect("LBRACE")
        while self._current_token.type != "RBRACE" and self._current_token.type != "EOF":
            kw = self._current_token.value
            if kw == "description":
                self._advance()
                self._expect("COLON")
                desc = self._expect("STRING")
                agent.description = desc.value
            elif kw == "type":
                self._advance()
                self._expect("COLON")
                agent.agent_type = self._expect("KEYWORD").value
            elif kw == "layer":
                self._advance()
                self._expect("COLON")
                agent.layer = self._expect("KEYWORD").value
            elif kw == "domain":
                self._advance()
                self._expect("COLON")
                agent.domain = self._advance().value
            elif kw == "input":
                self._advance()
                agent.inputs.append(self._parse_input())
            elif kw == "output":
                self._advance()
                agent.outputs.append(self._parse_output())
            elif kw == "tools":
                self._advance()
                agent.tools = self._parse_tool_list()
            elif kw == "capability":
                self._advance()
                agent.capabilities.append(self._parse_capability())
            elif kw == "body":
                self._advance()
                agent.body = self._parse_body()
            elif kw == "governance":
                self._advance()
                agent.governance = self._parse_governance()
            elif kw == "metadata":
                self._advance()
                agent.metadata = self._parse_metadata()
            else:
                self._advance()
        self._expect("RBRACE")
        return agent

    def _parse_input(self) -> DSLInput:
        name_tok = self._expect("IDENTIFIER", "KEYWORD")
        inp = DSLInput(name=name_tok.value, loc=self._create_loc(name_tok.loc))
        self._expect("LBRACE")
        while self._current_token.type != "RBRACE" and self._current_token.type != "EOF":
            kw = self._current_token.value
            if kw == "description":
                self._advance()
                self._expect("COLON")
                inp.description = self._expect("STRING", "KEYWORD").value
            elif kw == "data_type":
                self._advance()
                self._expect("COLON")
                inp.data_type = self._advance().value
            elif kw == "required":
                self._advance()
                self._expect("COLON")
                inp.required = self._advance().value == "true"
            else:
                self._advance()
        self._expect("RBRACE")
        return inp

    def _parse_output(self) -> DSLOutput:
        name_tok = self._expect("IDENTIFIER", "KEYWORD")
        out = DSLOutput(name=name_tok.value, loc=self._create_loc(name_tok.loc))
        self._expect("LBRACE")
        while self._current_token.type != "RBRACE" and self._current_token.type != "EOF":
            kw = self._current_token.value
            if kw == "description":
                self._advance()
                self._expect("COLON")
                out.description = self._expect("STRING", "KEYWORD").value
            elif kw == "data_type":
                self._advance()
                self._expect("COLON")
                out.data_type = self._advance().value
            else:
                self._advance()
        self._expect("RBRACE")
        return out

    def _parse_tool_list(self) -> list[DSLTool]:
        tools: list[DSLTool] = []
        self._expect("LBRACKET")
        while self._current_token.type not in ("RBRACKET", "EOF"):
            name = self._advance().value
            while self._match("DOT", "COLON"):
                name += "." + self._advance().value
            tools.append(DSLTool(name=name))
            self._match("COMMA")
        self._expect("RBRACKET")
        return tools

    def _parse_capability(self) -> DSLCapability:
        type_tok = self._expect("IDENTIFIER", "KEYWORD")
        self._expect("COLON")
        level = self._expect("KEYWORD", "IDENTIFIER").value
        return DSLCapability(capability_type=type_tok.value, level=level)

    def _parse_governance(self) -> DSLGovernance:
        gov = DSLGovernance()
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            val = self._advance().value
            if kw == "first_principles_check":
                gov.first_principles_check = val == "true"
            elif kw == "quality_gate_enabled":
                gov.quality_gate_enabled = val == "true"
            elif kw == "red_team_threshold":
                gov.red_team_threshold = val
            elif kw == "max_retries":
                gov.max_retries = int(val)
            elif kw == "token_budget":
                gov.token_budget = int(val)
        self._expect("RBRACE")
        return gov

    def _parse_metadata(self) -> DSLMetadata:
        meta = DSLMetadata()
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            if kw == "tags":
                self._expect("LBRACKET")
                tags = []
                while self._current_token.type not in ("RBRACKET", "EOF"):
                    tags.append(self._expect("STRING", "KEYWORD").value)
                    self._match("COMMA")
                self._expect("RBRACKET")
                meta.tags = tags
            elif kw == "author":
                meta.author = self._advance().value
            elif kw == "version":
                meta.version = self._advance().value
            elif kw == "license":
                meta.license = self._advance().value
            else:
                self._advance()
        self._expect("RBRACE")
        return meta

    def _parse_body(self) -> list[DSLNode]:
        stmts: list[DSLNode] = []
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            if kw == "step":
                stmts.append(self._parse_step())
            elif kw == "conditional_step":
                stmts.append(self._parse_conditional_step())
            elif kw == "condition":
                stmts.append(self._parse_condition())
            elif kw == "loop":
                stmts.append(self._parse_loop())
            elif kw == "parallel":
                stmts.append(self._parse_parallel())
            elif kw == "try_catch":
                stmts.append(self._parse_try_catch())
        self._expect("RBRACE")
        return stmts

    def _parse_step(self) -> DSLStep:
        name_tok = self._expect("IDENTIFIER", "KEYWORD")
        step = DSLStep(name=name_tok.value, loc=self._create_loc(name_tok.loc))
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            if kw == "call":
                step.call = self._parse_call()
            elif kw == "inputs":
                step.inputs = self._parse_inputs_dict()
            elif kw == "outputs":
                step.outputs = self._parse_outputs_dict()
            elif kw == "retry":
                step.retry = self._parse_retry()
        self._expect("RBRACE")
        return step

    def _parse_call(self) -> DSLCall:
        self._expect("LBRACE")
        call_type = "agent"
        name = ""
        skill_id = ""
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            if kw == "type":
                call_type = self._advance().value
            elif kw == "name":
                name = self._expect("IDENTIFIER", "KEYWORD").value
            elif kw == "skill_id":
                skill_id = self._expect("IDENTIFIER", "KEYWORD").value
            else:
                self._advance()
        self._expect("RBRACE")
        return DSLCall(type=call_type, name=name, skill_id=skill_id)

    def _parse_inputs_dict(self) -> dict[str, DSLExpression]:
        d: dict[str, DSLExpression] = {}
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            key = self._expect("IDENTIFIER", "KEYWORD", "STRING").value
            self._expect("COLON")
            d[key] = self._parse_expression()
            self._match("COMMA")
        self._expect("RBRACE")
        return d

    def _parse_outputs_dict(self) -> dict[str, str]:
        d: dict[str, str] = {}
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            k = self._expect("IDENTIFIER", "KEYWORD").value
            self._expect("COLON")
            v = self._expect("STRING", "IDENTIFIER", "KEYWORD").value
            d[k] = v
            self._match("COMMA")
        self._expect("RBRACE")
        return d

    def _parse_retry(self) -> DSLRetry:
        r = DSLRetry()
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            val = int(self._advance().value)
            if kw == "max_attempts":
                r.max_attempts = val
            elif kw == "backoff_ms":
                r.backoff_ms = val
        self._expect("RBRACE")
        return r

    def _parse_expression(self) -> DSLExpression:
        return self._parse_or()

    def _parse_or(self) -> DSLExpression:
        left = self._parse_and()
        while self._match("OR"):
            self._tokens[self._pos - 1]
            right = self._parse_and()
            left = DSLBinaryOp(operator="||", left=left, right=right)
        return left

    def _parse_and(self) -> DSLExpression:
        left = self._parse_comparison()
        while self._match("AND"):
            right = self._parse_comparison()
            left = DSLBinaryOp(operator="&&", left=left, right=right)
        return left

    def _parse_comparison(self) -> DSLExpression:
        left = self._parse_addition()
        while self._current_token.type in ("EQ", "NEQ", "LT", "GT", "LTE", "GTE"):
            op = self._advance().value
            right = self._parse_addition()
            left = DSLBinaryOp(operator=op, left=left, right=right)
        return left

    def _parse_addition(self) -> DSLExpression:
        left = self._parse_multiplication()
        while self._current_token.type in ("PLUS", "MINUS"):
            op = self._advance().value
            right = self._parse_multiplication()
            left = DSLBinaryOp(operator=op, left=left, right=right)
        return left

    def _parse_multiplication(self) -> DSLExpression:
        left = self._parse_unary()
        while self._current_token.type in ("STAR", "SLASH", "PERCENT"):
            op = self._advance().value
            right = self._parse_unary()
            left = DSLBinaryOp(operator=op, left=left, right=right)
        return left

    def _parse_unary(self) -> DSLExpression:
        if self._current_token.type in ("NOT", "MINUS", "PLUS"):
            op = self._advance().value
            operand = self._parse_unary()
            return DSLUnaryOp(operator=op, operand=operand)
        return self._parse_primary()

    def _parse_primary(self) -> DSLExpression:
        tok = self._current_token
        if tok.type == "NUMBER":
            self._advance()
            return DSLLiteral(value=float(tok.value) if "." in tok.value else int(tok.value))
        if tok.type == "BOOLEAN":
            self._advance()
            return DSLLiteral(value=tok.value == "true")
        if tok.type == "STRING":
            self._advance()
            return DSLLiteral(value=tok.value)
        if tok.value == "null":
            self._advance()
            return DSLLiteral(value=None)
        if tok.type == "LPAREN":
            self._advance()
            expr = self._parse_expression()
            self._expect("RPAREN")
            return expr
        if tok.type == "LBRACKET":
            return self._parse_array_literal()
        if tok.type in ("IDENTIFIER", "KEYWORD"):
            return self._parse_variable_or_call()
        if tok.type == "MINUS":
            self._advance()
            if self._current_token.type == "NUMBER":
                num = self._advance()
                return DSLLiteral(value=-float(num.value) if "." in num.value else -int(num.value))
            return DSLUnaryOp(operator="-", operand=DSLLiteral(value=0))
        self._error(f"Unexpected token: {tok.type} ('{tok.value}')", tok.loc)
        self._advance()
        return DSLLiteral(value=None)

    def _parse_array_literal(self) -> DSLArrayLiteral:
        self._match("LBRACKET")
        elems: list[DSLExpression] = []
        while self._current_token.type not in ("RBRACKET", "EOF"):
            elems.append(self._parse_expression())
            self._match("COMMA")
        self._expect("RBRACKET")
        return DSLArrayLiteral(elements=elems)

    def _parse_variable_or_call(self) -> DSLExpression:
        name = self._advance().value
        if self._match("LPAREN"):
            args: list[DSLExpression] = []
            while self._current_token.type != "RPAREN":
                args.append(self._parse_expression())
                self._match("COMMA")
            self._expect("RPAREN")
            return DSLFunctionCall(function=name, arguments=args)
        expr: DSLExpression = DSLVariable(name=name)
        while self._match("DOT", "LBRACKET"):
            if self._tokens[self._pos - 1].type == "DOT":
                prop = self._expect("IDENTIFIER", "KEYWORD").value
                expr = DSLPropertyAccess(object=expr, property=prop)
            else:
                idx = self._parse_expression()
                self._expect("RBRACKET")
                expr = DSLPropertyAccess(object=expr, property=str(idx))
        return expr

    def _parse_conditional_step(self) -> DSLConditionalStep:
        name_tok = self._expect("IDENTIFIER", "KEYWORD")
        step = DSLConditionalStep(name=name_tok.value, loc=self._create_loc(name_tok.loc))
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            if kw == "branches":
                step.branches = self._parse_branches()
            elif kw == "inputs":
                step.inputs = self._parse_inputs_dict()
            elif kw == "outputs":
                step.outputs = self._parse_outputs_dict()
        self._expect("RBRACE")
        return step

    def _parse_branches(self) -> list[ConditionalBranch]:
        branches: list[ConditionalBranch] = []
        self._expect("LBRACKET")
        while self._current_token.type not in ("RBRACKET", "EOF"):
            branch = ConditionalBranch()
            self._expect("LBRACE")
            while self._current_token.type not in ("RBRACE", "EOF"):
                kw = self._current_token.value
                self._advance()
                self._expect("COLON")
                if kw == "if":
                    branch.if_expr = self._parse_expression()
                elif kw == "then":
                    branch.then_call = self._parse_call()
                elif kw == "else":
                    branch.else_call = self._parse_call()
            self._expect("RBRACE")
            branches.append(branch)
            self._match("COMMA")
        self._expect("RBRACKET")
        return branches

    def _parse_condition(self) -> DSLCondition:
        cond = DSLCondition()
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            if kw == "test":
                cond.test = self._parse_expression()
        self._expect("RBRACE")
        return cond

    def _parse_loop(self) -> DSLLoop:
        loop = DSLLoop()
        type_tok = self._expect("IDENTIFIER", "KEYWORD")
        loop.loop_type = type_tok.value
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            if kw == "variable":
                loop.variable = self._advance().value
            elif kw == "test":
                loop.test = self._parse_expression()
            elif kw == "collection":
                loop.collection = self._parse_expression()
            elif kw == "body":
                loop.body = self._parse_body()
        self._expect("RBRACE")
        return loop

    def _parse_parallel(self) -> DSLParallel:
        p = DSLParallel()
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            if kw == "branches":
                p.branches = self._parse_branches_body()
            elif kw == "max_concurrency":
                val = self._advance()
                p.max_concurrency = int(val.value) if val.type == "NUMBER" else None
        self._expect("RBRACE")
        return p

    def _parse_branches_body(self) -> list[list[DSLNode]]:
        branches: list[list[DSLNode]] = []
        self._expect("LBRACKET")
        while self._current_token.type not in ("RBRACKET", "EOF"):
            branches.append(self._parse_body())
            self._match("COMMA")
        self._expect("RBRACKET")
        return branches

    def _parse_try_catch(self) -> DSLTryCatch:
        tc = DSLTryCatch()
        self._expect("LBRACE")
        while self._current_token.type not in ("RBRACE", "EOF"):
            kw = self._current_token.value
            self._advance()
            self._expect("COLON")
            if kw == "try_block":
                tc.try_block = self._parse_body()
            elif kw == "catch_variable":
                tc.catch_variable = self._advance().value
            elif kw == "catch_block":
                tc.catch_block = self._parse_body()
            elif kw == "finally_block":
                tc.finally_block = self._parse_body()
        self._expect("RBRACE")
        return tc
