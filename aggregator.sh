#!/bin/bash
# 1000 puslses = 1kwh
if [ -z "$1" ]; then
        echo Usage $0 measurements_file_path [day]
        exit 1
else
        FILE=$1
        DAY=$2
fi
# $1 day in month
# sets global variable DSUM
function calcDay {
        local day=$1
        DSUM=0
        LINES=`grep -a ^[0-9][0-9]\/$day $FILE`
        #echo Date: $day
        if [ -n "$LINES" ]; then
                for hr in {0..23}; do
                        if [ $hr -lt 10 ]; then
                                hr=0$hr
                        fi
                        LIST=$(echo "$LINES" | awk '{print $2, $3}' | grep ^$hr  | awk '{print $2}')
                        SUM=0
                        for m in $LIST; do
                                ((SUM += m))
                        done
                        echo $hr $SUM
                        ((DSUM += SUM)) # day summary update
                done
        fi
        DSUM_KW=$((DSUM / 1000))
        echo "Total ($day): $DSUM_KW kWh ($DSUM Wh) "
}
# main
if [ -n "$DAY" ]; then
        if [ $DAY -lt 10 ]; then
                DAY=0$DAY
        fi    
        calcDay $DAY
else
    MSUM=0
    for day in {1..31}; do
        if [ $day -lt 10 ]; then
                day=0$day
        fi
        echo Date: $day consumption by hr:
        calcDay $day    # sets global variable DSUM
        ((MSUM += DSUM)) # add daily to monthone
    done
    MSUM_KW=$((MSUM / 1000))
    echo "Total (month): $MSUM_KW kWh"
fi
