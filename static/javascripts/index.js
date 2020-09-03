$(function () {
    var $messages = $('.messages-content');

    $(window).load(function () {
        $messages.mCustomScrollbar();
    });


    var namespace = '';
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port + namespace);

    socket.on('connect', function () {
        //console.log('connected!');
        socket.emit('join', {room: 'A_Room'});
    });

    function updateScrollbar() {
        $messages.mCustomScrollbar("update").mCustomScrollbar('scrollTo', 'bottom', {
            scrollInertia: 10,
            timeout: 0
        });
    }

    function setDate(time) {
        $('<div class="timestamp">' + time + '</div>').appendTo($('.message:last'));
    }

    function insertMessage() {
        //console.log('insertMessage');
        var msg = $('.message-input').val();
        if ($.trim(msg) == '') {
            return false;
        }
        //console.log('send Inqueiry');
        var obj = {
            msg: msg,
            room: 'A_Room'
        };
        socket.emit('sendInquiry', obj);
    }

    function sendNickName(name) {
        var obj = {
            nick: name
        };
        var data_json = JSON.stringify(obj);
        console.log("send data!");
        $.ajax({
            url: "/set_nick",
            type: "POST",
            data: data_json,
            async: true,
            contentType: "application/json",
            success: function (data, textStatus, jqXHR) {
                console.log("data = ");
                console.log(data);
                if (data == "OK") {
                    location.reload();
                }
            }
        });
    }


    socket.on('getInquiry', function (msg) {
        //console.log(msg.msg);
        $('<div class="message new"><figure class="avatar"><img src="/static/mugshot/' + msg.PictureUrl + '" /></figure>' + msg.msg + '</div>').appendTo($('.mCSB_container')).addClass('new');
        setDate(msg.time);
        $('.message-input').val(null);
        updateScrollbar();
    });


    $('.message-submit').click(function () {
        insertMessage();
    });

    $(window).on('keydown', function (e) {
        if (e.which == 13) {
            insertMessage();
            return false;
        }
    });

    $('.setNick-submit').click(function () {
        var nickName = $('.setNick-input').val();
        if ($.trim(nickName) == '') {
            return false;
        }
        sendNickName(nickName);
    });


});