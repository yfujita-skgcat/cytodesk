#!/bin/bash
#
#

# エラー($? != 0)で止まるようにする.
#set -e
# エラー($? != 0)で止まらないようにする
#set +e
# 出力先を変更
#exec > log.log

#OPTION_STRING=hl:vd:n
declare -A HELP_OPTION_STRING
HELP_OPTION_STRING["h"]="Show help message."
HELP_OPTION_STRING["l:"]="Set log file."
HELP_OPTION_STRING["v"]="Show version."
HELP_OPTION_STRING["d:"]="Set log level."
HELP_OPTION_STRING["n"]="Dry-run mode."
HELP_OPTION_STRING["q"]="Quiet mode."

OPTION_STRING=$(echo ${!HELP_OPTION_STRING[@]} | sed -e 's/ //g')

# $1 = HELP_OPTION_STRING, Hashで渡し方は "$(declear -p HELP_OPTION_STRING)" で展開して渡す
# $2 = explanation
# $3 = arg_example
_usage()
{
  local f option_arg
  if [ "$1" != "" ]; then
    eval "local -A HELP_OPTION_STRING="${1#*=}   # 展開されたものをもう一度連想配列(Hash)に変更.
  fi
  local help_option=$(echo -n $(basename $0))
  local help_message=""
  for f in "${!HELP_OPTION_STRING[@]}"
  do
    if [ ! $(echo $f | grep ":" ) ]; then
      help_option="$help_option -$f"
      option_arg="    "  # スペースが効かない...
    else
      help_option="$help_option -$(echo -n $f | sed -e 's/://') arg"
      option_arg=" arg"
    fi
    help_message="$help_message\n-$(echo -n $f| sed -e 's/://')${option_arg}: ${HELP_OPTION_STRING[$f]}"
  done

  echo -n "$help_option "
  if [ "$3" = "" ]; then
     echo "test_argument"  # input arguments of this script
   else
     echo "$3"
   fi

  echo ""
  if [ "$2" = "" ]; then
    echo "Template script of bash"
  else
    echo "$2"
  fi

  # show options information
  echo -e "$help_message"
  # show footer informations
  echo ""
  echo "Example: $(echo -n $(basename $0)) -h"
  #echo "Example: ${FUNCNAME[1]} -h"   # 関数から_usage()を読んだ場合 .bash_functionなどで使う場合.
  if [ $# -eq 1 ]; then
    exit $1
  else
    exit 0
  fi

}


while getopts $OPTION_STRING OPT
do
  case $OPT in
    "h" )  # help
      FLAG_HELP="TRUE"
      ;;
    "l" )  # log file
      FLAG_LOG="TRUE"
      LOG_FILE=$OPTARG
      ;;
    "v" )  # version
      FLAG_VERSION="TRUE"
      ;;
    "d" )  # log level
      FLAG_LOGLEVEL="TRUE"
      LOG_LEVEL=$OPTARG
      ;;
    "n" )
      FLAG_DRY_RUN="TRUE"
      ;;
    "q" )
      FLAG_QUIET="TRUE"
      ;;
    ":"|"\?"|\?)
      #_usage 1
      #_usage "$(declare -p HELP_OPTION_STRING)" "" ""
      _usage
      exit 1
      ;;
  esac
done


if [ "$FLAG_HELP" = "TRUE" ];then
  #_usage "$(declare -p HELP_OPTION_STRING)" "" ""
  _usage
  exit 0
fi


if [ -n "$LOG_FILE" ]; then
  echo "IN FLAG_FILES = $LOG_FILE"
  exec > >(tee $LOG_FILE)
fi

if [ "$FLAG_VERSION" = "TRUE" ];then
  echo "Version 0.1"
  echo "bash $BASH_VERSION"
  exit 0
fi
if [ "$FLAG_LOG" = "TRUE" ]; then
  echo "log file is set to $LOG_FILE"
fi
if [ "$FLAG_LOGLEVEL" = "TRUE" ]; then
  echo "Log level is set to $LOG_LEVEL"
fi

# オプション部分切り捨て
shift $(($OPTIND - 1))

# debug function
# exec_command ()
# {
#   cmd_line="$1"
#   echo $cmd_line
#   if [ "$FLAG_DRY_RUN" != "TRUE" ]; then
#     eval "$cmd_line"
#   fi
# }

exec_command () {
  # local dry_run=0
  # local verbose=1
  local dry_run=0
  if [[ "$FLAG_DRY_RUN" == "TRUE" ]]; then
    dry_run=1
  else
    dry_run=0
  fi
  if [[ "$FLAG_QUIET" == "TRUE" ]]; then
    verbose=0
  else
    verbose=1
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      # -n|--dry-run)
      #   dry_run=1
      #   shift
      #   ;;
      # -q|--quiet)
      #   verbose=0
      #   shift
      #   ;;
      --)
        shift
        break
        ;;
      -*)
        echo "exec_command: unknown option: $1" >&2
        return 2
        ;;
      *)
        break
        ;;
    esac
  done

  if [[ $# -eq 0 ]]; then
    echo "exec_command: command is missing" >&2
    return 2
  fi

  if [[ "$verbose" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  fi

  if [[ "$dry_run" -eq 1 ]]; then
    return 0
  fi

  exec "$@"
}



#==========================================
# script region
#==========================================

# file=/path/to/dir/file.sh
# ${file##*/} => file.sh  (最長一致)
# ${file##*.} => sh (最長一致)
# ${file%/*}  => /path/to/dir (後方から最短一致削除, / まで末端から削除 => direname)
# ${file%.*} => /path/to/dir/file  (拡張子だけ除く)

# echo "\$0 = $0"
# echo '$#' = $#
# echo "\$@ = $@"

cd "$(dirname "$0")" || exit 1
exec direnv exec . make gui
