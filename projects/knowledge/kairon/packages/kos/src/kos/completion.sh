# KOS CLI Bash Completion
# Source: source kos/completion.sh

_kos_cli() {
    local cur prev words cword
    _init_completion || return

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=($(compgen -W "domains list status search research ingest onto help" -- "$cur"))
        return
    fi

    case "${words[1]}" in
        search|research)
            COMPREPLY=($(compgen -W "--format --limit --domains --zone --kind --json" -- "$cur"))
            ;;
        status)
            COMPREPLY=($(compgen -W "--format --domain --json" -- "$cur"))
            ;;
        domains|list)
            COMPREPLY=($(compgen -W "--format --limit --json" -- "$cur"))
            ;;
        onto)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=($(compgen -W "extract infer rebuild card path discover graph list" -- "$cur"))
            fi
            ;;
    esac
} && complete -F _kos_cli kos
